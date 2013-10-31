#!/usr/bin/env python
# ==========================================================================
#
# Copyright (C) 2013 RidgeRun, LLC (http://www.ridgerun.com)
# All Rights Reserved.
#
# Author: Jose Pablo Carballo <jose.carballo@ridgerun.com>
#
# The contents of this software are proprietary and confidential to RidgeRun,
# LLC.  No part of this program may be photocopied, reproduced or translated
# into another programming language without prior written consent of 
# RidgeRun, LLC.
#
# Serial communication operations to support the installer.
#
# ==========================================================================

# ==========================================================================
# Imports
# ==========================================================================

import os
import re
import time
import rrutils
import rrutils.hexutils as hexutils
from uboot import UbootTimeoutException

# ==========================================================================
# Constants
# ==========================================================================

# TFTP settings
DEFAULT_TFTP_DIR = '/srv/tftp'
DEFAULT_TFTP_PORT = 69

# NAND
DEFAULT_NAND_TIMEOUT = 60 # seconds
DEFAULT_NAND_BLK_SIZE = 131072 # bytes
DEFAULT_NAND_PAGE_SIZE = 2048 # bytes

# Installation

DEFAULT_KERNEL_EXTRA_BLKS = 3
DEFAULT_FS_EXTRA_BLKS = 19

# ==========================================================================
# Public Classes
# ==========================================================================

class NandInstaller(object):
    
    def __init__(self, uboot, nand_block_size=0, nand_page_size=0,
                 ram_load_addr=None, dryrun=False, interactive=True):
        """
        :param uboot: :class:`Uboot` instance.
        :param nand_block_size: NAND block size (bytes). If not given, the
            value will be obtained from uboot (once).
        :param nand_page_size: NAND page size (bytes). If not given, the
            value will be obtained from uboot (once).
        :param ram_load_addr: RAM address to load components, in decimal or
            hexadecimal (`'0x'` prefix).
        :param dryrun: Enable dryrun mode. System commands will be logged,
            but not executed.
        :type dryrun: boolean
        :param interactive: Enable interactive mode. The user will
            be prompted before executing dangerous commands.
        :type interactive: boolean
        """
        
        self._l = rrutils.logger.get_global_logger()
        self._e = rrutils.executer.Executer()
        self._e.logger = self._l
        self._u = uboot
        self._nand_block_size = nand_block_size
        self._nand_page_size = nand_page_size
        self._ram_load_addr = None
        if hexutils.is_valid_addr(ram_load_addr):
            self._ram_load_addr = hexutils.str_to_hex(str(ram_load_addr))
        self._dryrun = dryrun
        self._e.dryrun = dryrun
        self._u.dryrun = dryrun
        self._interactive = interactive

    def __set_nand_block_size(self, size):
        self._nand_block_size = int(size)

    def __get_nand_block_size(self):
        
        # Don't query uboot if already set
        if self._nand_block_size != 0:
            return self._nand_block_size
        
        self._u.cmd('nand info', prompt_timeout=None)
        
        if self._dryrun: # no need to go further in this mode
            self.nand_block_size = DEFAULT_NAND_BLK_SIZE
            return self._nand_block_size
        
        device_found, line = self._u.expect('Device 0')
        if not device_found:
            self._l.error('Can\'t find Device 0')
            return 0
        
        # Two versions of uboot output:
        # old: Device 0: Samsung K9K1208Q0C at 0x2000000 (64 MB, 16 kB sector)
        # new: Device 0: NAND 256MiB 1,8V 16-bit, sector size 128 KiB
        m = re.match('.* (?P<size_kb>\d+) (kb|kib).*', line, re.IGNORECASE)
        if m:
            self._nand_block_size = int(m.group('size_kb')) << 10 # to bytes
        else:
            self._l.error('Unable to determine the NAND block size')
        return self._nand_block_size
    
    nand_block_size = property(__get_nand_block_size, __set_nand_block_size, 
                           doc="""NAND block size (bytes). The value will be
                           obtained from uboot (once), unless manually
                           specified.""")
    
    def __set_nand_page_size(self, size):
        self._nand_page_size = int(size)
    
    def __get_nand_page_size(self):
        
        # Don't query uboot if already set
        if self._nand_page_size != 0:
            return self._nand_page_size
        
        page_size = 0
        possible_sizes=['0200', '0400', '0800', '1000']
        
        if self._dryrun:
            for size in possible_sizes:
                self._u.cmd('nand dump.oob %s' % size, prompt_timeout=None)
            self._nand_page_size = DEFAULT_NAND_PAGE_SIZE
            return self._nand_page_size
        
        for size in possible_sizes:
            
            self._u.cmd('nand dump.oob %s' % size, prompt_timeout=None)
            found, line = self._u.expect('Page 0000')
            if not found: continue
            
            # Detect the page size upon a change on the output
            m = re.match('^Page 0000(?P<page_size>\d+) .*', line)
            if m:
                page_size = int(m.group('page_size'), 16)
                if page_size != 0:
                    break
                
        if page_size == 0:
            self._l.error('Unable to determine the NAND page size')
        else:
            self._nand_page_size = page_size
        return self._nand_page_size
    
    nand_page_size = property(__get_nand_page_size, __set_nand_page_size,
                          doc="""NAND page size (bytes). The value will be
                           obtained from uboot (once), unless manually
                           specified.""")

    def __set_ram_load_addr(self, ram_load_addr):
        if hexutils.is_valid_addr(ram_load_addr):
            self._ram_load_addr = hexutils.to_hex(str(ram_load_addr))
        else:
            self._l.error('Invalid RAM load address: %s' %
                               ram_load_addr)
            self._ram_load_addr = None
        
    def __get_ram_load_addr(self):
        return self._ram_load_addr
    
    ram_load_addr = property(__get_ram_load_addr, __set_ram_load_addr,
                               doc="""Uboot RAM load address, in decimal or
                                hexadecimal (`'0x'` prefix).""")
    
    def __set_dryrun(self, dryrun):
        self._dryrun = dryrun
        self._e.dryrun = dryrun
        self._u.dryrun = dryrun
    
    def __get_dryrun(self):
        return self._dryrun
    
    dryrun = property(__get_dryrun, __set_dryrun,
                     doc="""Enable dryrun mode. System commands will be
                     logged, but not executed.""")
    
    def __set_interactive(self, interactive):
        self._interactive = interactive
    
    def __get_interactive(self):
        return self._interactive
    
    interactive = property(__get_interactive, __set_interactive,
                           doc="""Enable interactive mode. The user will
                           be prompted before executing dangerous commands.""")
    
    def _check_icache(self):
        """
        Checks availability of the 'icache' uboot command.
        """
        
        self._u.cmd('icache', prompt_timeout=None)
        found_icache = self._u.expect('Instruction Cache is')[0]
        if not found_icache:
            self._l.error("Your uboot doesn't have icache command, refusing "
               "to continue due to the risk of hanging, you can update your "
               "bootloader by other means like an SD card.")
            return False
        return True    

    def _load_file_to_ram(self, filename, load_addr):
        raise NotImplementedError

    def load_uboot_to_ram(self, img_filename, load_addr):
        """
        Loads an uboot image to RAM and executes it. This uboot will drive
        the installation.
        
        :param img_filename: Path to the uboot image file.
        :param load_addr: Load address in RAM where to load the uboot image.
        """
        
        ret = self._u.sync()
        if ret is False: return False
        
        ret = self._check_icache()
        if re is False: return False
        
        self._l.info("Storing the current uboot's bootcmd")
        prev_bootcmd = self._u.get_env('bootcmd')
        self._u.set_env('bootcmd', '')
        self._u.save_env()
        
        self._l.info('Loading new uboot to RAM')
        ret = self._load_file_to_ram(img_filename, load_addr)
        if ret is False: return False
        
        self._l.info('Running the new uboot')
        self._u.cmd('icache off')
        self._u.cmd('go %s' % load_addr)
        time.sleep(2) # Give time to uboot to restart
        ret = self._u.sync()
        if ret is False:
            self._l.error('Failed to detect the new uboot starting')
            return False
        
        if prev_bootcmd:
            self._l.info('Restoring the previous uboot bootcmd')
            self._u.set_env('bootcmd', prev_bootcmd)
        
        self._u.save_env()
        return True
    
    def install_ubl(self, img_filename, start_blk):
        """
        Installs the UBL (initial program loader) image to NAND.
        
        :param img_filename: Path to the UBL image file.
        :param start_blk: Start block in NAND for the UBL image.
        :type start_blk: integer
        :returns: Returns true on success; false otherwise.
        """
        
        self._l.info("Loading UBL image to RAM")
        ret = self._load_file_to_ram(img_filename, self._ram_load_addr)
        if ret is False: return False
        
        offset_addr = start_blk * self.nand_block_size
        img_size = os.path.getsize(img_filename)
        img_size_blk = (img_size / self.nand_block_size) + 1
        img_size_aligned = img_size_blk * self.nand_block_size
        
        self._l.info("Erasing UBL NAND space")
        cmd = 'nand erase %s %s' % (hex(offset_addr), hex(img_size_aligned))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=DEFAULT_NAND_TIMEOUT)
        
        self._l.info("Writing UBL image from RAM to NAND")
        cmd = 'nand write.ubl %s %s %s' % (self._ram_load_addr,
                                   hex(offset_addr), hex(img_size_aligned))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=None)
        
        return True
    
    def install_uboot(self, img_filename, start_blk):
        """
        Installs the uboot image to NAND.
        
        :param img_filename: Path to the uboot image file.
        :param start_blk: Start block in NAND for the uboot image.
        :type start_blk: integer
        :returns: Returns true on success; false otherwise.
        """
    
        self._l.info("Loading uboot image to RAM")
        ret = self._load_file_to_ram(img_filename, self._ram_load_addr)
        if ret is False: return False

        offset_addr = start_blk * self.nand_block_size
        img_size = os.path.getsize(img_filename)
        img_size_blk = (img_size / self.nand_block_size) + 1
        img_size_aligned = img_size_blk * self.nand_block_size

        self._l.info("Erasing uboot NAND space")
        cmd = 'nand erase %s %s' % (hex(offset_addr), hex(img_size_aligned))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=DEFAULT_NAND_TIMEOUT)
        
        self._l.info("Writing uboot image from RAM to NAND")
        cmd = 'nand write.ubl %s %s %s' % (self._ram_load_addr,
                                       hex(offset_addr), hex(img_size_aligned))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=None)
        
        self._l.info("Restarting to use the uboot in NAND")
        self._u.cmd('reset', prompt_timeout=None)
        found_reset_str = self._u.expect('U-Boot', timeout=10)[0]
        if not found_reset_str:
            self._l.error("Failed to detect the uboot in NAND restarting")
            return False
        time.sleep(4) # Give uboot time to initialize
        ret = self._u.sync()
        if ret is False:
            self._l.error("Failed synchronizing with the uboot in NAND")
            return False
        
        return True

    def _md5sum(self, filename):
        cmd = "md5sum %s | cut -f1 -d' '" % filename
        ret, md5sum = self._e.check_output(cmd)
        return md5sum.strip() if ret == 0 else ''
    
    def _is_kernel_install_needed(self, img_filename, start_blk):
        # Detect a difference in either the md5sum or the offset
        md5sum = self._md5sum(img_filename)
        md5sum_on_board = self._u.get_env('kernelmd5sum')
        kernel_off = hex(start_blk * self.nand_block_size)
        kernel_off_on_board = self._u.get_env('kerneloffset') # hex
        if md5sum != md5sum_on_board or kernel_off != kernel_off_on_board:
            return True
        return False

    def _is_fs_install_needed(self, img_filename, start_blk):
        # Detect a difference in either the md5sum or the offset
        md5sum = self._md5sum(img_filename)
        md5sum_on_board = self._u.get_env('fsmd5sum')
        fs_off = hex(start_blk * self.nand_block_size)
        fs_off_on_board = self._u.get_env('fsoffset') # hex
        if md5sum != md5sum_on_board or fs_off != fs_off_on_board:
            return True
        return False

    def _install_img(self, filename, comp, comp_nick, start_blk, size_blks,
                     extra_blks):
        offset_addr = start_blk * self.nand_block_size
        img_size = os.path.getsize(filename)
        img_size_blks = (img_size / self.nand_block_size)
        if (img_size % self.nand_block_size != 0):
            img_size_blks += 1
        img_size_blks += extra_blks
        img_size_aligned = img_size_blks * self.nand_block_size
        part_size = img_size_aligned 
        if size_blks:
            if img_size_blks > size_blks:
                self._l.warning("Using %s NAND blocks instead of %s for the "
                            "%s partition" % (img_size_blks, size_blks, comp))
            else:
                part_size = size_blks * self.nand_block_size
                
        self._l.info("Loading %s image to RAM" % comp)
        ret = self._load_file_to_ram(filename, self._ram_load_addr)
        if ret is False: return False
        
        self._u.set_env('autostart', 'yes')
        
        self._l.info("Erasing %s NAND space" % comp)
        cmd = 'nand erase %s %s' % (hex(offset_addr), hex(part_size))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=DEFAULT_NAND_TIMEOUT)
        
        self._l.info("Writing %s image from RAM to NAND" % comp)
        cmd = 'nand write %s %s %s' % (self._ram_load_addr, 
                                       hex(offset_addr), hex(img_size_aligned))
        self._u.cmd(cmd, echo_timeout=None, prompt_timeout=DEFAULT_NAND_TIMEOUT)
        self._u.set_env('%ssize' % comp_nick, hex(img_size_aligned))
        self._u.set_env('%spartitionsize' % comp_nick, hex(part_size))
        self._u.set_env('%smd5sum' % comp_nick, self._md5sum(filename))
        self._u.set_env('%soffset' % comp_nick, hex(offset_addr))
        self._u.save_env()
        return True

    def install_kernel(self, img_filename, start_blk, size_blks=None,
                   extra_blks=DEFAULT_KERNEL_EXTRA_BLKS, force=False):
        """
        Installs the kernel image to NAND. After installing the image it
        will save in uboot's environment the following variables:
        
        * `koffset`: Kernel offset address, hexadecimal.
        * `kmd5sum`: Kernel image md5sum.
        * `ksize`: Kernel size, in bytes.
        * `kpartitionsize`: Kernel partition size, block aligned, in bytes.
        
        This information is also used to avoid re-installing the image if it is
        not necessary, unless `force` is specified.
        
        :param img_filename: Path to the kernel image file.
        :param start_blk: Start block in NAND for the kernel image.
        :type start_blk: integer
        :param size_blks: Size in blocks for the kernel partition. If None,
            the size will be calculated using the size of the image and 
            the extra blocks.
        :type size_blks: integer
        :param extra_blks: Extra NAND blocks to reserve for the kernel.
        :type extra_blks: integer
        :param force: Forces the kernel installation.
        :type force: boolean
        :returns: Returns true on success; false otherwise.
        """
        
        is_needed = self._is_kernel_install_needed(img_filename, start_blk) 
        if not force and not is_needed:
            self._l.info("Kernel doesn't need to be installed")
            return True
        
        return self._install_img(img_filename, 'kernel', 'k', start_blk,
                                 size_blks, extra_blks)
    
    def install_fs(self, img_filename, start_blk, size_blks=None,
                   extra_blks=DEFAULT_FS_EXTRA_BLKS, force=False):
        """
        Installs the filesystem image to NAND. After installing the image it
        will save in uboot's environment the following variables:
        
        * `fsoffset`: Filesystem offset address, hexadecimal.
        * `fsmd5sum`: Filesystem image md5sum.
        * `fssize`: Filesystem size, in bytes.
        * `fspartitionsize`: Filesystem partition size, block aligned, in bytes.
        
        This information is also used to avoid re-installing the image if it is
        not necessary, unless `force` is specified.
        
        :param img_filename: Path to the filesystem image file.
        :param start_blk: Start block in NAND for the filesystem image.
        :type start_blk: integer
        :param size_blks: Size in blocks for the filesystem partition. If None,
            the size will be calculated using the size of the image and 
            the extra blocks.
        :type size_blks: integer
        :param extra_blks: Extra NAND blocks to reserve for the filesystem.
        :type extra_blks: integer
        :param force: Forces the filesystem installation.
        :type force: boolean
        :returns: Returns true on success; false otherwise.
        """
        
        is_needed = self._is_fs_install_needed(img_filename, start_blk) 
        if not force and not is_needed:
            self._l.info("Filesystem doesn't need to be installed")
            return True
        
        return self._install_img(img_filename, 'filesystem', 'fs', start_blk,
                                 size_blks, extra_blks)

    def install_cmdline(self, cmdline, force=False):
        """
        Installs the kernel command line to uboot's environment. If the same
        command line has already been installed it will avoid re-installing it, 
        unless `force` is specified.

        :param cmdline: Kernel command line.
        :param force: Forces the kernel command line installation.
        :type force: boolean
        :returns: Returns true on success; false otherwise.
        """
        
        cmdline = cmdline.strip()
        cmdline_on_board = self._u.get_env('bootargs')        
        if cmdline == cmdline_on_board and not force:
            self._l.info("Kernel command line doesn't need to be installed")
            return True
        self._u.set_env('bootargs', cmdline)
        self._u.save_env()
        return True

    def install_bootcmd(self, bootcmd, force=False):
        """
        Installs the boot command (`bootcmd`) to uboot's environment. If the
        same boot command has already been installed it will avoid
        re-installing it, unless `force` is specified.

        :param bootcmd: Boot command.
        :param force: Forces the boot command installation.
        :type force: boolean
        :returns: Returns true on success; false otherwise.
        """
        
        bootcmd = bootcmd.strip()
        bootcmd_on_board = self._u.get_env('bootcmd')        
        if bootcmd == bootcmd_on_board and not force:
            self._l.info("Boot command doesn't need to be installed")
            return True
        self._u.set_env('bootcmd', bootcmd)
        self._u.set_env('autostart', 'yes') 
        self._u.save_env()
        return True

class NandInstallerTFTP(NandInstaller):
    
    #: Static networking mode.
    MODE_STATIC = 'static'
    
    #: DHCP networking mode.
    MODE_DHCP = 'dhcp'
    
    def __init__(self, uboot, nand_block_size=0, nand_page_size=0,
                 ram_load_addr=None, dryrun=False, interactive=True,
                 host_ipaddr='', target_ipaddr='', tftp_dir=DEFAULT_TFTP_DIR,
                 tftp_port=DEFAULT_TFTP_PORT, net_mode=None):
        """
        :param uboot: :class:`Uboot` instance.
        :param nand_block_size: NAND block size (bytes). If not given, the
            value will be obtained from uboot (once).
        :param nand_page_size: NAND page size (bytes). If not given, the
            value will be obtained from uboot (once).
        :param ram_load_addr: RAM address to load components, in decimal or
            hexadecimal (`'0x'` prefix).
        :param dryrun: Enable dryrun mode. System commands will be logged,
            but not executed.
        :type dryrun: boolean
        :param interactive: Enable interactive mode. The user will
            be prompted before executing dangerous commands.
        :type interactive: boolean
        :param host_ipaddr: Host IP address.
        :param target_ipaddr: Target IP address, only necessary
            in :const:`MODE_STATIC`.
        :param tftp_dir: TFTP root directory.
        :param tftp_port: TFTP server port.
        :type tftp_port: integer
        :param net_mode: Networking mode. Possible values:
            :const:`MODE_STATIC`, :const:`MODE_DHCP`.
        """    
        NandInstaller.__init__(self, uboot, nand_block_size, nand_page_size,
                               ram_load_addr, dryrun, interactive)
        self._tftp_dir = tftp_dir
        self._tftp_port = tftp_port
        self._net_mode = net_mode
        self._host_ipaddr = host_ipaddr
        self._target_ipaddr = target_ipaddr
        self._is_network_setup = False
        
    def __set_tftp_port(self, port):
        self._tftp_port = port
    
    def __get_tftp_port(self):
        return self._tftp_port
    
    tftp_port = property(__get_tftp_port, __set_tftp_port,
                     doc="""TFTP server port.""")
    
    def __set_tftp_dir(self, directory):
        self._tftp_dir = directory
    
    def __get_tftp_dir(self):
        return self._tftp_dir
    
    tftp_dir = property(__get_tftp_dir, __set_tftp_dir,
                     doc="""TFTP root directory.""")

    def __set_net_mode(self, mode):
        self._net_mode = mode
    
    def __get_net_mode(self):
        return self._net_mode
    
    net_mode = property(__get_net_mode, __set_net_mode,
                     doc="""Networking mode. Possible values:
                     :const:`MODE_STATIC`, :const:`MODE_DHCP`.""")

    def __set_target_ipaddr(self, ipaddr):
        self._target_ipaddr = ipaddr
    
    def __get_target_ipaddr(self):
        return self._target_ipaddr
    
    target_ipaddr = property(__get_target_ipaddr, __set_target_ipaddr,
                     doc="""Target IP address, only necessary in
                     :const:`MODE_STATIC`.""")

    def __set_host_ipaddr(self, ipaddr):
        self._host_ipaddr = ipaddr
    
    def __get_host_ipaddr(self):
        return self._host_ipaddr
    
    host_ipaddr = property(__get_host_ipaddr, __set_host_ipaddr,
                     doc="""Host IP address.""")

    def _check_tftp_settings(self):
        """
        Checks TFTP settings in the host (dir and port).
        """
        
        cmd = 'netstat -an | grep udp | grep -q :%d' % self._tftp_port
        ret = self._e.check_call(cmd)
        if ret != 0:
            self._l.error("Seems like you aren't running tftp udp server on "
              "port %d, please check your server settings" % self._tftp_port)
            return False
        
        return True

    def _load_file_to_ram(self, filename, load_addr):
        if not self._is_network_setup:
            self._l.error("Please setup uboot's network prior to any TFTP "
                          "transfer")
            return False
        
        # Copy the file to the host's TFTP directory
        basename = os.path.basename(filename)
        tftp_filename = '%s/%s' % (self._tftp_dir, basename)
        cmd = 'cp %s %s' % (filename, tftp_filename)
        ret, output = self._e.check_output(cmd)
        if ret != 0:
            self._l.error(output)
            return False
        
        # Estimate a transfer timeout - 10 seconds per MB
        size_b = os.path.getsize(tftp_filename)
        one_mb = 1 << 20
        transfer_timeout = ((size_b/one_mb) + 1) * 10
        
        # Transfer
        hex_load_addr = hexutils.to_hex(load_addr)
        self._l.debug("Starting TFTP transfer from file '%s' to RAM address "
                      "'%s'" % (tftp_filename, hex_load_addr))
        cmd = 'tftp %s %s' % (hex_load_addr, basename)
        try:
            self._u.cmd(cmd, prompt_timeout=transfer_timeout)
        except UbootTimeoutException:
            self._u.cancel_cmd()
            self._l.error("TFTP transfer failed from '%s:%s'." %
                               (self._host_ipaddr, self._tftp_port))
            return False
        
        filesize = self._u.get_env('filesize')
        if filesize:
            env_size_b = int(filesize, base=16)
        else:
            env_size_b = 0
        if size_b != env_size_b and not self._dryrun:
            self._l.error("Something went wrong during the transfer, the size "
                "of file '%s' (%s) differs from the transferred bytes (%s)"
                % (tftp_filename, size_b, filesize))
            return False
        
        return True
        
    def setup_uboot_network(self):
        """
        Setup networking for uboot, based on the specified :func:`net_mode`.
        
        Returns true on success; false otherwise.
        """
        
        if not self._net_mode:
            self._l.error('Please provide a networking mode')
            return False
        
        if (self._net_mode == NandInstallerTFTP.MODE_STATIC and 
                not self._target_ipaddr):
            self._l.error('No IP address specified for the target.')
            return False
        
        self._l.info('Checking TFTP settings')
        ret = self._check_tftp_settings()
        if ret is False: return False
        
        self._l.info('Configuring uboot network')
        if self._net_mode == NandInstallerTFTP.MODE_STATIC:
            self._u.set_env('ipaddr', self._target_ipaddr)
        elif self._net_mode == NandInstallerTFTP.MODE_DHCP:
            self._u.set_env('autoload', 'no')
            self._u.set_env('autostart', 'no')
            self._u.cmd('dhcp', prompt_timeout=None)
            # If dhcp failed at retry 3, stop and report the error
            dhcp_error_line = 'BOOTP broadcast 3'
            found_error, line = self._u.expect(dhcp_error_line, timeout=6)
            if found_error and not self.dryrun:
                self._u.cancel_cmd()
                msg = ("Looks like your network doesn't have dhcp enabled or "
                       "you don't have an ethernet link. ")
                if line:
                    msg += "This is the log of the last line: %s" % line
                self._l.error(msg)
                return False

        self._u.set_env('serverip', self._host_ipaddr)
        self._is_network_setup = True
        
        return True