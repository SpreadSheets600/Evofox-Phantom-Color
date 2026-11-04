src_file=evofox-phantom.py
exe_file=$(shell echo ${src_file} | cut -d . -f 1)
install_dir=/usr/local/bin

install: ${src_file}
	cp ./${src_file} ${install_dir}/${exe_file}

uninstall:
	rm ${install_dir}/${exe_file}

# --- INSTANT / Anko RGB mouse (30fa:1440) ---
share_dir=/usr/local/share/evofox-phantom
anko_files=anko-mouse.py anko-color.py anko-1440-profile.hex

install-anko: ${anko_files}
	install -d ${share_dir}
	install -m 644 anko-1440-profile.hex ${share_dir}/
	install -m 755 anko-mouse.py anko-color.py ${share_dir}/
	ln -sf ${share_dir}/anko-mouse.py ${install_dir}/anko-mouse
	ln -sf ${share_dir}/anko-color.py ${install_dir}/anko-color

# Optional (Linux): lets the logged-in user use the tools without sudo
install-udev: 99-anko-mouse.rules
	install -m 644 99-anko-mouse.rules /etc/udev/rules.d/
	udevadm control --reload-rules
	udevadm trigger --subsystem-match=hidraw

uninstall-anko:
	rm -rf ${share_dir}
	rm -f ${install_dir}/anko-mouse ${install_dir}/anko-color
	rm -f /etc/udev/rules.d/99-anko-mouse.rules
