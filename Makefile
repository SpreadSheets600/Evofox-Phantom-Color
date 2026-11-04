src_file=archive/evofox-phantom.py
exe_file=evofox-phantom
install_dir=/usr/local/bin

install: ${src_file}
	cp ./${src_file} ${install_dir}/${exe_file}

uninstall:
	rm ${install_dir}/${exe_file}

share_dir=/usr/local/share/evofox-phantom
efp_files=efp-color.py efp-1440-profile.hex

install-efp: ${efp_files}
	install -d ${share_dir}
	install -m 644 efp-1440-profile.hex ${share_dir}/
	install -m 755 efp-color.py ${share_dir}/
	ln -sf ${share_dir}/efp-color.py ${install_dir}/efp-color

install-udev: 99-efp-mouse.rules
	install -m 644 99-efp-mouse.rules /etc/udev/rules.d/
	udevadm control --reload-rules
	udevadm trigger --subsystem-match=hidraw

uninstall-efp:
	rm -rf ${share_dir}
	rm -f ${install_dir}/efp-color
	rm -f /etc/udev/rules.d/99-efp-mouse.rules
