# What is this?

This is a set of ansible playbooks for helping set up an environment to run the
tests.

## How do you use this?

Pick the OS type that most closely resembles your test environment.

For example, to run on Fedora, RHEL, or similar:

```bash
cd redhat
```

Create an inventory file like this:

`mytesthost.domain ansible_user=mytestuser`

The ansible_user should have sudo privileges.  Preferably, set up password-less
ssh and password-less sudo for that user, though you can instead instruct
ansible to ask for passwords.

Then run the playbook:

```bash
ansible-playbook -i inventory setup.yml
```

## What about Debian?

Similarly to the redhat case above, there is an `ubuntu` playbook that may also
work with Debian.
