# Configuration

You can easily modify default settings of `aosc-mkrawimg` by editing `config.yml`.

## Settings fields

Each setting is defined as a key, and treir values are vary, depends on the settings itself.

Also, you can easily override these settings by providing corresponding command line options.

### General configuration

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `workdir` | string | `/var/cache/aosc-mkrawimg` | Specify the working directory. If the target does not exist, it will try to create one. |
| `mntprefix` | string | `/mnt/mkrawimg` | Specify the mount point prefix, the mount paths will create here. |
| `logfile` | string | `mkrawimg.log` | Specify the log file name. The logfile will be placed in the working directory. |
| `noupgrade` | bool | `no` | Skip the upgrade process after OS extraction. Reduces network usage. |
| `nocleanup` | bool | `no` | Skip cleaning up the working directory. |
| `norecreate` | bool | `no` | Skip the image creation, use the previously created image. |
| `verbose` | bool | `no` | Enable verbose output. The verbose output will still write to the log file. | 

### OS Postinstall settings

This section defines the behavior of all post-OS setup process.

| Key | Type | Default | Description |
| :-- | :-- | :-- | :-- |
| `lang` | string | `os.environ["LANG"]` | Language will be used in target OS |
| `timezone` | string | `Asia/Shanghai` | Timezone will be used in target OS |
| `hostname` | string | `aosc-:devicename:` | Default host name for the OS |
| `createuser` | bool | `yes` | Specify whether to create a built-in user |
| `username` | string | `aosc` | Default built-in non-root user for the target OS |
| `password` | string | `anthon` | Default password for the built-in user |
| `fullname` | string | `AOSC OS Built-in User` | Full name for the built-in user |
| `group` | string | `audio,video,tty,wheel` | Groups the built-in user will be in - Use comma ( `,` ) to separate groups |
| `sudo-nopasswd` | bool | `yes` | Disable password in sudo for the built-in user |
| `method` | string | `tarball` | Method to install OS. See below. |
| `bootstrap` | list of string | - | List of packages will be preinstalled using bootstrap method |


#### Hostname placeholders

A device have four different names, and these can be used to generate a hostname. For what these names actually mean, please see [SPEC.md](SPEC.md).

1. `device-id` which is the device name in a defined device path, e.g. `rpi-4b` .
2. `device-name` which is the full name of the variant, but every space and other symbol is replaced by dashes ( `-` ), e.g. `Raspberry-Pi-4B` .
3. `platform-id` which is the DEVICE name in the path, e.g. `rpi4` .
4. `platform-name` which is the full name of the DEVICE, e.g. `Raspberry-Pi-4-Series`.

#### OS install methods

There are two methods will be implemented in the program.

1. `tarball` - Download a OS tarball and extrsct it directly into the filesystem. You can specify a list of packages which will be installed later in the command-line options.
2. `bootstrap` - Use `aoscbootstrap` utility to bootstrap a customized installation, which means that you can choose what package to install, and you still can specify a list of packages which will be installed later in the command-line options.
