#!/usr/bin/sudo /usr/bin/python3

import argparse
import logging
import os
import platform
import subprocess
import sys
from typing import List

import yaml

VERSION = ('0', '1', '0')
AUTHORS = ['Cyanoxygen <cyanoxygen@aosc.io>']
LICENSE = 'GPLv3'
REPO = ''
# RESDIR: directory where these config files and devices file placed.
#         Default is $PWD, but can be changed if the main program file is separated with configs.
if os.path.exists('config.yml'):
    RESDIR = os.path.abspath('.')
else:
    RESDIR = os.path.abspath('/usr/lib/aosc-mkrawimg-py/')

SARGS = [
    ['-v', '--verbose', 'Enable debug output', 'store_true', False],
    ['-U', '--noupdate', 'Skip the upgrade process after OS extraction', 'store_true', False],
    ['-C', '--nocleanup', 'Skip cleaning up the working directory', 'store_true', False],
    ['-R', '--norecreate', 'Skip the image creation, use the previously created image', 'store_true', False],
]
VARGS = [
    ['-f', '--osfile', 'Specify an AOSC OS tarball', 'store', 'aosc-os_base_arm64_latest.tar.xz', str],
    ['-d', '--workdir', 'Specify the work directory', 'store', '/var/cache/mkrawimg', str],
    ['-l', '--logfile', 'Specify where to place the log file', 'store', 'mkrawimg.log', str],
    ['-m', '--mntprefix', 'Specify the prefix path of mount points', 'store', '/mnt/mkrawimg', str],
    ['-V', '--variants', 'Specify the OS variant e.g. cinnamon', 'store', 'base', str],
]
allowed_vals = {
    'method': ['tarball', 'bootstrap'],
    'map': ['mbr', 'gpt'],
    'fs_req': ['vfat', 'ext4']
}

if __name__ == '__main__':
    if platform.system() != 'Linux':
        print('This is not a joke, please run the program in Linux!', file=sys.stderr)
        exit(1)

    # Enforce root user execution
    if os.getuid() != 0:
        print("Please run me as root, thanks. Exiting.", file=sys.stderr)
        exit(1)

# Get current directory
# May never used, use RESDIR instead.
PWD = os.path.abspath('.')
DEVICES = f'{RESDIR}/devices'


#
#   Logging configuration
#
# This section configures the logging module, sets up a logger with two outputs.
# One is the logfile, and the other is the console output.
class Jobs:
    def __init__(self):
        self.jobqueue: List['Job'] = []
        self.curjob = None

    def run(self):
        while len(self.jobqueue) > 0:
            try:
                self.curjob = self.jobqueue.pop(0)
                self.curjob.make()
            except OhJesusTaskFailed:
                self.curjob.errclean()


class Logger:
    """
    A simple logger class.
    """

    def __init__(self, fmt: str = '%(asctime)-23s | %(levelname)-8s | %(message)s') -> None:
        self.format = fmt
        self.logfile = ''
        self.logger: logging.Logger = logging.Logger('mkrawimg')
        self.logformatter: logging.Formatter = logging.Formatter(self.format)
        self.console: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        self.nullhandler: logging.FileHandler = logging.FileHandler('/dev/null')
        self.filehandler = self.nullhandler
        self.loglevel = 'INFO'

        self.console.setFormatter(self.logformatter)
        self.nullhandler.setFormatter(self.logformatter)

        self.logger.addHandler(self.console)
        self.logger.addHandler(self.nullhandler)

        self.logger.setLevel(self.loglevel)

        self.altformatter = logging.Formatter(fmt="%(asctime)-23s | %(message)s")
        self.altlogger = logging.Logger('mkrawimg')
        self.altlogger.setLevel(logging.INFO)
        self.althandler = logging.FileHandler('/dev/null')
        self.althandler.setFormatter(self.altformatter)

    def setup(self, logfile: str):
        self.logfile = logfile
        try:
            self.filehandler = logging.FileHandler(self.logfile)
            self.logger.addHandler(self.filehandler)
        except (OSError, FileNotFoundError):
            self.filehandler = self.nullhandler
            self.err("Failed to setup a logfile. Disabling logging into logfile.")

    def info(self, *kwargs):
        self.logger.info(*kwargs)

    def debug(self, *kwargs):
        self.logger.debug(*kwargs)

    def crit(self, *kwargs):
        self.logger.critical(*kwargs)

    def warn(self, *kwargs):
        self.logger.critical(*kwargs)

    def err(self, *kwargs):
        self.logger.error(*kwargs)

    def setlevel(self, level=logging.INFO):
        self.logger.setLevel(level)

    def setupalternatelogger(self) -> str:
        import random, string
        rdstr = ''.join(random.sample(string.ascii_letters, 8))
        try:
            self.althandler = logging.FileHandler(f'/tmp/aosc-mkrawimg-{rdstr}.log')
            self.altlogger.addHandler(self.althandler)
        except Exception as e:
            raise OSError("Failed to setup temp log file") from e
        return f'/tmp/aosc-mkrawimg-{rdstr}.log'

    def logtofile(self, string):
        return self.altlogger.info(string)


logger = Logger()


#
#   Utility functions
#
def bailout(msg: str = ''):
    logger.crit(f'A critical err occurred! {msg}')
    logger.crit('Can not proceed. Bailing out.')
    sys.exit(1)


# noinspection PyRedeclaration
class OhJesusTaskFailed(Exception):
    """
    Oh Jesus! A task failed! Need to abort!
    """

    def __init__(self, task: str, msg: str) -> None:
        super().__init__(msg)
        self.warn = msg
        self.stderr = f'Jesus: Task {task} failed: {msg}! Can\'t continue.'
        self.task = task
        logger.crit(self.stderr)

    def __init__(self, task: str) -> None:
        super().__init__()
        self.task = task
        self.stderr = f'Jesus: Task {task} failed! Can\'t continue.'
        logger.crit(self.stderr)

    def __str__(self) -> str:
        return self.stderr


class OhJesusProgramExitAbnormally(Exception):
    """
    Oh Jesus! The program just returned non-zero status!
    """

    def __init__(self, proc: subprocess.CompletedProcess, msg: str = "") -> None:
        super().__init__()
        self.proc = proc
        if msg:
            self.givenmsg = msg
            self.stderr = f'Jesus: {msg}'
        else:
            self.givenmsg = ''
            self.stderr = f'Jesus: {self.proc.args[0]} returned non-zero status {self.proc.returncode}.'
        logger.crit(self.stderr)

    def __str__(self) -> str:
        return self.stderr


class OhJesusProgramNotFound(Exception):
    """
    Oh Jesus! The program you are trying to execute is not found!
    """

    def __init__(self, exe: str) -> None:
        super().__init__()
        self.exe = exe
        self.stderr = f'Jesus: executable {self.exe} not found!'
        logger.crit(self.stderr)

    def __str__(self) -> str:
        return self.stderr


def exc(exe: list, path: str = None, inp: str = None, test: bool = False) -> subprocess.CompletedProcess:
    """
    Execution with subprocess.run()
    Returns a CompletedProcess object.
    Records stdout and stderr.
    """
    if test:
        logger.info(f"Executing with subprocess.run {exe}, PWD={path}")
        return subprocess.run('true')
    logger.debug(f'Executing with subprocess.run {exe}, PWD={path}')
    try:
        ret = subprocess.run(args=exe, cwd=path, input=inp, encoding='utf-8',
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise OhJesusProgramNotFound(exe[0]) from e

    logger.debug('stdout:')
    for i in ret.stdout.splitlines():
        logger.debug(i)
        if logger.logger.level != logging.DEBUG:
            logger.logtofile(i)

    logger.debug("stderr:")
    for i in ret.stderr.splitlines():
        logger.debug(i)
        if logger.logger.level != logging.DEBUG:
            logger.logtofile(i)

    if ret.returncode != 0:
        raise OhJesusProgramExitAbnormally(ret)
    return ret


class Loadable:
    """
    A basic class with load() function using black magic (__setattr__()).
    Most of classes in this program will inherit from this so it is not necessary to write a load() function.
    """

    def __init__(self):
        pass

    def load(self, spec: dict):
        """
        Load partition spec from a dict, using black magic.

        :param spec: dict to load
        :return: None
        """
        for key in spec:
            deftype = type(self.__getattribute__(key))
            keytype = type(spec[key])
            if keytype != deftype:
                logger.warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.__dict__:
                logger.warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.__setattr__(key, spec[key])


class Job(Loadable):
    def __init__(self):
        super().__init__()

    def make(self):
        """
        Stub make() function.
        :raises: OhJesusTaskFailed
        """
        raise NotImplementedError

    def errclean(self):
        """
        If error occurs, this function is called to clean up the mess.
        """
        raise NotImplementedError


#
#   The configuration class
#
class AppConfig:
    """
    Holds the default app configuration, and loads config.yml.
    This class holds the `general' section of config.yml.
    TODO refactor to inherit from loadable class.
    """

    class _OSConfig:
        """
        This class holds os-install section of config.yml.
        """

        def __init__(self):
            self.lang: str = str(os.environ['LANG']) if 'LANG' in os.environ else 'en_US.UTF-8'
            self.timezone: str = 'Asia/Shanghai'
            self.hostname: str = 'aosc-:variantname'
            self.createuser: bool = True
            self.username: str = 'aosc'
            self.password: str = 'anthon'
            self.fullname: str = 'AOSC OS Built-In User'
            self.groups: str = 'audio,video,tty,wheel,adm'
            self.nopasswd: bool = True
            self.method: str = 'tarball'
            self.bootstrap: list = ['base']

        def __format__(self, format_spec: str) -> str:
            return ''

    def __init__(self):
        self.workdir: str = '/var/cache/aosc-mkrawimg'
        self.mntprefix: str = '/mnt/mkrawimg'
        self.logfile: str = 'mkrawimg.log'
        self.noupgrade: bool = False
        self.nocleanup: bool = False
        self.norecreate: bool = False
        self.verbose: bool = False
        self.osfile: str = ''
        self.variant: str = 'base'

        self.OSConfig = self._OSConfig()

    def load_from_file(self):
        """
        Load a config.yml file.
        TODO replace with a simple load().
        """
        confname = f'{RESDIR}/config.yml'
        if not os.path.isfile(confname):
            logger.warn('Unable to find config.yml. Using default configuration.')
            return

        try:
            conffile = open(confname, 'r')
        except OSError as e:
            logger.warn(f'Unable to open config.yml: {e.errno} {e.strerror}.')
            logger.warn('Using default configuration.')
            return
        except Exception as e:
            logger.warn(f'Unable to open config.yml: {e}. Using default configuration.')
            return
        conf = yaml.safe_load(conffile)

        # This is the real magic
        for key in conf['general']:
            deftype = type(self.__getattribute__(key))
            keytype = type(conf['general'][key])
            if keytype != deftype:
                logger.warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.__dict__:
                logger.warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.__setattr__(key, conf['general'][key])
        # load OSConfig in the same way
        for key in conf['os-install']:
            deftype = type(self.OSConfig.__getattribute__(key))
            keytype = type(conf['os-install'][key])
            if keytype != deftype:
                logger.warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.OSConfig.__dict__:
                logger.warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.OSConfig.__setattr__(key, conf['os-install'][key])

    def load_from_args(self, args: argparse.Namespace):
        # This is the real magic, again
        for key in args.__dict__:
            self.__setattr__(key, args.__dict__[key])


Config: AppConfig = AppConfig()


class Environment:
    """
    Environment: Class to check system environment.

    It checks if the system meets the minimum requirements,
    e.g. loop device support, and filesystem tools suite, binfmt support,
    and QEMU static emulators to support binfmt.
    Checks are done during .check(), any unmet requirements will result in a immidiate bailout.
    """

    def __init__(self) -> None:
        self.supported_fs: list = ['vfat', 'ext4']
        self.arch: str = ''
        self.os: str = ''
        self.loop_support = False
        self.binfmt = False

    @staticmethod
    def check_supported_fs() -> list:
        """
        Check available filesystem
        """
        ret = []
        output = []
        output.extend(os.listdir('/usr/bin'))
        output.extend(os.listdir('/usr/sbin'))

        for item in output:
            if item[0:5] == 'mkfs.':
                ret.append(item[5:])
        return ret

    @staticmethod
    def check_arch() -> str:
        arch = platform.machine()
        return arch

    @staticmethod
    def check_binfmt() -> bool:
        # TODO raise an exception instead
        try:
            with open('/proc/sys/fs/binfmt_misc/status') as f:
                supported = (f.read() == 'enabled\n')  # bool
        except (FileNotFoundError, OSError):
            supported = False

        if supported:
            if len(os.listdir('/proc/sys/fs/binfmt_misc/')) <= 2:
                # Restart binfmt first
                subprocess.run(['systemctl', 'restart', 'systemd-binfmt.service'])
                if len(os.listdir('/proc/sys/fs/binfmt_misc/')) > 2:
                    return False
                logger.warn('Your system supports binfmt, but no foreign architecture support is enabled.')
                logger.warn('Please ensure you have qemu and qemu-user-static installed.')
                supported = False
        else:
            logger.warn('Your system does not support binfmt_misc.')
            logger.warn('You can only make OS images for same architecture of your machine.')
        return supported

    @staticmethod
    def check_loop() -> bool:
        # Raise an exception about this.
        loopdev = subprocess.getoutput('losetup -f')
        loop_support = ('/dev/loop' in loopdev)
        if not loop_support:
            logger.err('It looks like there is no loop device support for your kernel.')
            logger.err('We are trying to fix this by manually loading `loop\' kernel module.')
            ret = subprocess.call(['modprobe', 'loop'])
            if not ret:
                loop_support = True
            else:
                logger.err('Oops, your system does not have loop device support which this tool requires.')
                loop_support = False
        return loop_support

    def check(self):
        self.loop_support = self.check_loop()
        if not self.loop_support:
            bailout('Requirement does not meet: loop device')
        self.supported_fs = self.check_supported_fs()
        if not set(self.supported_fs).issuperset(allowed_vals['fs_req']):
            logger.err('Oops, please make sure e2fsprogs and dosfstools are installed and try again.')
            bailout(f'Missing basic filesystem support: {" and ".join(allowed_vals["fs_req"])}')
        self.arch = self.check_arch()
        self.binfmt = self.check_binfmt()


class Device(Job):
    def __init__(self):
        """
        Loads a device configuration.
        Loads a default value of all possible options first, then call load().
        """
        super().__init__()
        self.arch: str = Env.arch
        self.id = 'x86_64-bios'
        self.platformid = 'x86_64-generic'
        self.platformname = 'Generic x86_64 machine'
        self.platformdesc = 'Image for Generic x86_64 machine'
        self.path = ['x86_64', 'generic', self.id]
        self.desc = 'Image for Legacy BIOS machines'

    def make(self):
        pass

    def errclean(self):
        pass


#
#   Device-related class
#
class Partition(Job):
    """
    Defines a partition.
    """
    option_label = {
        'vfat': '-n',
        'ext4': '-L',
        'btrfs': '-L'
    }

    def __init__(self, parent: 'Image'):
        super().__init__()
        self.path: str = '/dev/loop0'
        self.num: int = 1
        self.name: str = 'aosc'
        self.size: int = -1
        self.type: str = '83'
        self.fs: str = 'ext4'
        self.mount: str = '/'
        self.bootable: bool = True
        self.mountopt: str = ''
        self.flash: False
        self.file: str = ''
        self.ready: bool = False
        self.image = parent

    def gen_plan(self):
        """
        Generate a sfdisk(8) script. One partition at a time.
        """
        TYPE_MBR = 'type=0x{}, '
        TYPE_GPT = 'type={}, '
        SIZE = 'size={0}MiB, '
        SIZEREST = ''
        BOOTABLE = 'bootable, '
        # sfdisk(8) input per partition
        plan = ''
        # Partition type
        if self.image.map == 'mbr':
            plan += TYPE_MBR.format(self.type)
        else:
            plan += TYPE_GPT.format(self.type)
        # Partition size
        if self.size > 0:
            plan += SIZE.format(self.size)
        else:
            plan += SIZEREST
        if self.bootable:
            plan += BOOTABLE
        return plan

    def make_fs(self):
        """
        Format a partition (making filesystems).

        :return: None
        :raise: OSError
        if called program returned non-zero.
        """
        if (not self.fs) or self.type == '05':
            # In case of an extended partition, there's no point to make an fs here.
            return
        if self.fs not in Env.supported_fs:
            logger.crit(f'Filesystem {self.fs} is not supported in this system.')
            logger.crit('Treating as an critical err.')
            raise OhJesusTaskFailed('make_fs', f'Unsupported filesystem: {self.fs}.')
        exe = f'mkfs.{self.fs}'
        opts = [exe]
        if self.name:
            opts.extend([self.option_label.get(self.fs, '-L'), self.name])
        opts.extend([f'{self.path}p{self.num}'])
        res = exc(opts)
        if res.returncode != 0:
            raise OhJesusTaskFailed('make_fs', f"Failed to make filesystem {self.fs} at {self.path}p{self.num}.")

    def make(self):
        """
        Function called by Image.make() after the plain image is make.
        """
        try:
            logger.info(f'{self.__class__.__name__}: Making filesystem {self.num}...')
            self.make_fs()
        except OhJesusTaskFailed as e:
            # Chain this to the Image.make() to fail.
            raise e from e

    def errclean(self):
        pass


class Image(Job):
    """
    Class repesents an image.
    To make an actual image, call make().
    """

    def __init__(self, device: Device):
        super().__init__()
        self.variant: str = 'base'
        self.loopdev: str = '/dev/loop0'
        self.imgpath: str = Config.workdir
        self.filename: str = 'aosc-os_amd64_base.img'
        self.size: int = 5120
        self.sector: int = 512
        self.start: int = 2048
        self.map: str = 'mbr'
        self.device = device
        self.parts: List[Partition] = []

    def gen_plan(self):
        """
        Generate sfdisk(8) input.
        """
        logger.info(f"{self.__class__.__name__}: Applying partition map...")
        plan = [f'label: {self.map}']
        for i in self.parts:
            plan.append(i.gen_plan())
        logger.info(f'{self.__class__.__name__}: generated plan:\n{plan}')
        return '\n'.join(plan)

    def apply_map(self):
        logger.info(f'{self.__class__.__name__}: Applying partition map...')
        plan = self.gen_plan()
        ret = exc(['sfdisk', f'{self.imgpath}/{self.filename}'], inp=plan)
        if ret.returncode != 0:
            raise OhJesusTaskFailed('apply_map', "Failed to run sfdisk(8).")

    def mount(self):
        self.loopdev = exc(['losetup', '--find']).stdout

    def make(self):
        # Create an empty image
        logger.info(f'{self.__class__.__name__}: Creating an empty image...')
        try:
            exe = ['dd', 'if=/dev/zero', f'of={self.imgpath}/{self.filename}', 'bs=1MiB', f'count={self.size}']
            ret = exc(exe)
            if ret.returncode != 0:
                raise OhJesusTaskFailed('make_image', 'Failed to create an image.')
            # Apply partition map and load it into loop
            self.apply_map()
            for i in self.parts:
                logger.info(f'Making partition {i.num}...')
                i.make()
        except (OhJesusTaskFailed, OhJesusProgramExitAbnormally) as e:
            # TODO add cleanup process
            bailout(e)

    def errclean(self):
        pass


Env: Environment = Environment()
Devices: List[Device] = []
DevPath: dict = {}


def main():
    global Config, Env
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description='An utility to generate ready-to-flash AOSC OS images.',
        epilog=f'(C) {", ".join(AUTHORS)}. This program is licensed under {LICENSE}. \
        For more information please refer to {REPO}.'
    )
    for arg in VARGS:
        parser.add_argument(arg[0], arg[1], help=arg[2], action=arg[3], default=arg[4], type=arg[5])
    for arg in SARGS:
        parser.add_argument(arg[0], arg[1], help=arg[2], action=arg[3], default=arg[4])
    parser.add_argument('device', help='Target device to make an image for')
    args = parser.parse_args()

    logger.info(f'Welcome to aosc-mkrawimg v{".".join(VERSION)}!')
    logger.info('Reading config file.')
    Config.load_from_file()
    Config.load_from_args(args)
    logger.info('Checking environments.')
    Env.check()

    # Switch to debug as soon as we can, if either command line or config has enabled it.
    # Now the config is loaded and the command line options are parsed,
    # we really need to do this now.
    # For debug purpose.
    if args.verbose or Config.verbose:
        logger.setlevel(logging.DEBUG)
        logger.debug('DEBUG output enabled!')
        logger.debug('Now your console output could be really messy ^o^')
    logger.debug('Loaded command options:')
    for key in args.__dict__:
        logger.debug(f'{key:<12}: {str(args.__dict__[key]):<}')
    logger.debug('Loaded config:')
    for key in Config.__dict__:
        logger.debug(f'{key:<12}: {Config.__dict__[key]:<}')
    for key in Config.OSConfig.__dict__:
        logger.debug(f'{key:<12}: {str(Config.OSConfig.__dict__[key]):<}')


if __name__ == '__main__':
    main()
