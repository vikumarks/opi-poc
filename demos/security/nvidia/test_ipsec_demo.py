import grpc
import netmiko
import pydpu
import pytest
import snappi
import time
from pprint import pprint as pp
import os
import sys
sys.path.insert(0,'/home/opi/opi-poc/demos')
sys.path.insert(1,'/home/opi/opi-poc/demos/security/nvidia')
sys.path.insert(2,'..')
import datetime
from testbed import *
from RESTasV3 import RESTasV3
from tabulate import tabulate
# replace with pydpu code
import ipsec_pb2
import ipsec_pb2_grpc


@pytest.fixture(scope='session')
def dpu():
    dpu_info = {
        'device_type': 'linux',
        'host': B_DYP_IP,
        'username': DYP_USER,
        'password': DYP_PASSWORD
    }
    dpu_connect = netmiko.ConnectHandler(**dpu_info)
    dpu_connect.send_command('ip addr add 200.0.0.1/24 dev %s' % B_DYP_INTERFACES[0])
    dpu_connect.send_command('ip addr add 201.0.0.1/24 dev %s' % B_DYP_INTERFACES[1])
    dpu_connect.send_command('sysctl net.ipv4.ip_forward=1')
    dpu_connect.send_command('iptables -P FORWARD ACCEPT')
    dpu_connect.send_command('systemctl stop firewalld')
    dpu_connect.send_command('systemctl disable firewalld')
    dpu_connect.send_command('systemctl start docker')

    command = 'docker run --rm --network host --mount src=/var/run,target=/var/run,type=bind --name opi-strongswan-bridge -d ghcr.io/opiproject/opi-strongswan-bridge:main /opi-vici-bridge -port=50151'
    print(command)
    output = dpu_connect.send_command(command)
    print(output)

    # idealy replace as many of those ssh commands with OPI API as they become available

    yield dpu_connect

    dpu_connect.send_command('ip addr del 200.0.0.1/24 dev  %s' % B_DYP_INTERFACES[0])
    dpu_connect.send_command('ip addr del 201.0.0.1/24 dev  %s' % B_DYP_INTERFACES[1])
    dpu_connect.send_command('docker stop opi-strongswan-bridge')
    dpu_connect.send_command('ip neigh flush 200.0.0.0/8')
    dpu_connect.send_command('ip neigh flush 201.0.0.0/8')


@pytest.fixture(scope='session')
def server():

    server_info = {
        'device_type': 'linux',
        'host': TGEN1_IP,
        'username': 'root',
        'password': 'wrinkle#B52'
    }
    server_connect = netmiko.ConnectHandler(**server_info)

    print(os.getcwd())
    command = 'docker compose --progress plain -f /home/opi/opi-poc/demos/security/nvidia/deployment/cyperf_with_ipsec.yml up -d'
    print(command)
    output = server_connect.send_command(command, read_timeout=30)
    print(output)

    command = "docker top ClientAgent | grep startup.sh | sed -n '1p' | awk '{ print $2 }' | xargs -I{} sudo ip link set %s netns {} name %s" % (TGEN1_INTERFACES[0],TGEN1_INTERFACES[0])
    print(command)
    output = server_connect.send_command(command)
    print(output)
    command = "docker top ServerAgent | grep startup.sh | sed -n '1p' | awk '{ print $2 }' | xargs -I{} sudo ip link set %s netns {} name %s" % (TGEN1_INTERFACES[1], TGEN1_INTERFACES[1])
    print(command)
    output = server_connect.send_command(command)
    print(output)
    command = 'docker exec ClientAgent bash -c "cyperfagent interface test set %s;ip link set up dev %s"' % (TGEN1_INTERFACES[0],TGEN1_INTERFACES[0])
    print(command)
    output = server_connect.send_command(command)
    print(output)
    command = 'docker exec ServerAgent bash -c "cyperfagent interface test set %s;ip link set up dev %s"' % (TGEN1_INTERFACES[1], TGEN1_INTERFACES[1])
    print(command)
    output = server_connect.send_command(command)
    print(output)
    time.sleep(30)

    yield server_connect
    command = 'docker compose --progress plain -f /home/opi/opi-poc/demos/security/nvidia/deployment/cyperf_with_ipsec.yml down'
    print(command)
    output = server_connect.send_command(command,read_timeout=30)
    print(output)


def test_server_to_server_via_ipsec_and_dpu(dpu, server):

    print('connecting to opi')
    channel = grpc.insecure_channel('%s:50151' % B_DYP_IP)
    stub = ipsec_pb2_grpc.IPsecServiceStub(channel)

    stub.IPsecVersion(ipsec_pb2.IPsecVersionRequest())

    stub.IPsecStats(ipsec_pb2.IPsecStatsRequest())

    print('configuring the tunnel')
    tun1_0_0 = ipsec_pb2.IPsecLoadConnRequest(
        connection=ipsec_pb2.Connection(
            name='tun1_0_0',
            version='2',
            local_addrs=[ipsec_pb2.Addrs(addr='200.0.0.1')],
            remote_addrs=[ipsec_pb2.Addrs(addr='200.0.0.2')],
            local_auth=ipsec_pb2.LocalAuth(
                auth=ipsec_pb2.AUTH_TYPE_PSK,
                id='200.0.0.1'
            ),
            remote_auth=ipsec_pb2.RemoteAuth(
                auth=ipsec_pb2.AUTH_TYPE_PSK,
                id='200.0.0.2'
            ),
            children=[ipsec_pb2.Child(
                name='tun1_0_0',
                esp_proposals=ipsec_pb2.Proposals(
                    crypto_alg=[ipsec_pb2.CRYPTO_ALGORITHM_AES128],
                    integ_alg=[ipsec_pb2.INTEG_ALGORITHM_SHA1]
                ),
                remote_ts=ipsec_pb2.TrafficSelectors(
                    ts=[ipsec_pb2.TrafficSelectors.TrafficSelector(
                        cidr='40.0.0.0/24'
                    )]
                ),
                local_ts=ipsec_pb2.TrafficSelectors(
                    ts=[ipsec_pb2.TrafficSelectors.TrafficSelector(
                        cidr='201.0.0.0/24'
                    )]
                ),
            )],
            proposals=ipsec_pb2.Proposals(
                crypto_alg=[ipsec_pb2.CRYPTO_ALGORITHM_AES128],
                integ_alg=[ipsec_pb2.INTEG_ALGORITHM_SHA384],
                dhgroups=[ipsec_pb2.DH_GROUPS_MODP1536]
            )
        )
    )

    connection_1 = stub.IPsecLoadConn(tun1_0_0)

    rest = RESTasV3(ipAddress=CYPERF_IP)
    rest.wait_agents_connect(agents_nr=2)
    response = rest.get_agents()
    for res in response:
        print(res['AgentTags'], type(res['AgentTags']),res['IP'])

    agents_IPs = (response[1]['IP'],response[0]['IP']) if 'Server' in response[0]['AgentTags'][0]  else (response[0]['IP'],response[1]['IP'])
    print(agents_IPs)

    def wait_test_finished(timeout=300):
        def collect_stats():
            result_id = rest.get_test_id()
            stats_to_get = [('client-action-statistics',False),('ipsec-tunnels-total',True)]
            os.system('clear')
            for stat,transpose in stats_to_get:
                stats = rest._RESTasV3__sendGet('/api/v2/results/{}/stats/{}'.format(result_id, stat), 200, debug=False).json()
                headers = stats['columns']
                #import pdb;pdb.set_trace()
                if 'snapshots' not in stats:continue
                rows = stats['snapshots'][-1]['values']
                if transpose:
                    rows.insert(0,headers)
                    rows = list(zip(*rows))
                    headers=[]
                print("\n\n",stat,"\n")
                print(tabulate(rows, headers=headers, tablefmt="github"))
            time.sleep(.5)

        response = rest.get_test_status()
        actual_duration = 0
        counter = 1
        while actual_duration < rest.testDuration + timeout:
            response = rest.get_test_status()
            if response['status'] == 'STOPPING' and not rest.stopTrafficTime:
                rest.stopTrafficTime = rest._RESTasV3__getEpochTime()
            if response['status'] == 'STOPPED':
                if response['testElapsed'] >= response['testDuration']:
                    print('Test gracefully finished')
                    rest.stopTime = rest._RESTasV3__getEpochTime()
                    return rest.stopTime
                else:
                    raise Exception("Error! Test stopped before reaching the configured duration = {}; Elapsed = {}"
                                    .format(response['testDuration'], response['testElapsed']))
            else:
                print('Test duration = {}; Elapsed = {}'.format(response['testDuration'], response['testElapsed']))
            actual_duration += counter
            collect_stats()
            time.sleep(counter)
        else:
            print("Test did not stop after timeout {}s. Test status= {}. Force stopping the test!".format(timeout,response['status']))
            rest.stop_test()
            raise Exception("Error! Test failed to stop after timeout {}s.".format(timeout))



    # CyPerf API test with 1 imported test config. This is where we keep all the test configs.
    rest.setup('opi-ipsec.zip')
    rest.assign_agents_by_ip(agents_ips=agents_IPs[0], network_segment=1)
    rest.assign_agents_by_ip(agents_ips=agents_IPs[1], network_segment=2)
    rest.set_test_duration(30)
    rest.start_test()
    wait_test_finished()
    rest.delete_current_session()

