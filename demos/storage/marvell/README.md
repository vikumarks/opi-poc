# Storage demo

## Video

See <https://www.youtube.com/watch?v=TEpdQryRj6A>

## API

[API protobufs](https://github.com/opiproject/opi-api/tree/main/storage)

## Server

see <https://hub.docker.com/r/opiproject/opi-marvell-bridge>

```Shell
$ docker run --rm -it -v /var/tmp/:/var/tmp/ -p 50051:50051 ghcr.io/opiproject/opi-marvell-bridge:main
2022/11/29 00:03:55 plugin serevr is &{{}}
2022/11/29 00:03:55 server listening at [::]:50051
```

## Client

see <https://github.com/opiproject/pydpu> and <https://github.com/opiproject/godpu>
