# Static-site deployment

The rendered catalog is served at `https://docs.michaelspost.com/` as an
ordinary static nginx site. The public edge terminates TLS and forwards the
original hostname through the existing tunnel to the web host's loopback nginx
listener. The origin does not expose a new public port.

Rendercase is not part of this path. Its scheduled uploader remains disabled,
and deploying the static site must not create or update an artifact.

## Managed components

This repository owns:

- the complete validation and MkDocs build;
- synchronization of the generated `dist/` tree;
- the dedicated nginx virtual host and document root;
- public verification after deployment.

The infrastructure repository owns the tunnel hostname mapping. Public DNS is
managed through RillDNS rather than committed zone files. Environment-specific
host aliases and deployment identities remain in the ignored Ansible inventory.

## Configure a controller

Copy the example inventory and replace the placeholder with the deployment
host visible from the controller:

```sh
cd ansible
cp inventory.example inventory
```

Optional document-root, ownership, and verification overrides belong in the
ignored `group_vars/all.yml`, starting from `group_vars/all.yml.example`.

## Preview and deploy

The playbook runs the complete repository validation before it can synchronize
with deletion enabled. Preview the filesystem and nginx changes with:

```sh
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local \
ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote \
ansible-playbook --check --diff playbook.yml
```

Deploy and verify the public HTTPS endpoint with:

```sh
ANSIBLE_LOCAL_TEMP=/tmp/ansible-local \
ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote \
ansible-playbook playbook.yml
```

For the first deployment only, set `docs_verify_url=` until tunnel routing and
DNS exist, then rerun without that override for the public verification step.
The playbook validates nginx before reloading it and leaves the existing site
untouched if the local documentation build fails.

## Rollback

Static content can be rolled back by checking out the previous known-good site
commit and rerunning the playbook. Remove the tunnel and DNS mappings first if
the hostname itself must be withdrawn. Do not delete the shared nginx listener
or modify the main site's document root; the documentation uses its own virtual
host and directory.
