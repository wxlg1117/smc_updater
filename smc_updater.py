import os
import time
import sys
import re
import json
import cli_ui
import delegator
import logging
import urllib.request
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from pyvirtualdisplay import Display

manual_run = True

sum_bin = "./sum_2.1.0_Linux_x86_64/sum"

ipmicfg_bin = "./IPMICFG_1.29.0_build.181029/Linux/64bit/IPMICFG-Linux.x86_64"

alpha_dict = {
	"a":0,
	"b":1,
	"c":2,
	"d":3,
	"e":4,
	"f":5,
	"g":6,
	"h":7,
	"i":8,
	"j":9
}

""" Check if a process ID is valid or not (signal 0 doesn't kill anything)"""
def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

""" Test if the system is using UEFI or BIOS"""
""" Some BIOS updates are seperated by these types"""
def is_uefi_boot():
	return os.path.isdir("/sys/firmware/efi")

def get_board_model():
	return delegator.chain("sudo dmidecode -t baseboard|grep 'Product Name: ' |sed 's/Product Name: //' | tr -d '[:space:]'").out

def get_current_bios():
	return delegator.chain("sudo dmidecode -t bios| grep Version |sed 's/Version://' |tr -d '[:space:]'").out

def get_current_ipmi():
	return delegator.chain("sudo ./IPMICFG_1.29.0_build.181029/Linux/64bit/IPMICFG-Linux.x86_64 -ver | awk -F ':' {'print $2'}| tr -d [:space:]").out

def update_ipmi(ipmi_bin):
	logging.info("update_ipmi() | Running IPMI Update With {0}".format(ipmi_bin))
	print("Updating with {0}".format(ipmi_bin))
	ipmi_update = delegator.run("sudo {0} -c UpdateBmc --file {1}".format(sum_bin, ipmi_bin), block=False, timeout=600)
	timer = 0
	print(ipmi_update.pid)
	while check_pid(ipmi_update.pid):
		print("Updating IPMI....This may take up to 10 minutes. [ Elapsed Time: {0}m ]".format(str(timer)))
		time.sleep(60)
		timer += 1
	print("IPMI Update Complete")
	logging.info(ipmi_update)
	logging.info("main::update_ipmi() | IPMI Update Complete {0}".format(ipmi_bin))
	
def update_bios(bios_bin):
	print("Updating BIOS with {0}".format(bios_bin))
	logging.info("main::update_bios() | Running BIOS update with {0}".format(bios_bin))
	bios_update = delegator.run("sudo {0} -c UpdateBios --file {1}".format(sum_bin, bios_bin), block=False, timeout=600)
	timer = 0
	while check_pid(bios_update.pid):
		print(bios_update.pid)
		print("Updating BIOS....This may take up to 10 minutes. [ Elapsed Time: {0}m ]".format(str(timer)))
		time.sleep(60)
		timer += 1
	if 'Manual steps are required' in bios_update.out:
		print("Automated BIOS Update Failed: Please Reboot System And Try Again")
		logging.error("main::update_bios() | BIOS Update Failed")
		logging.error(bios_update)
	else:
		logging.info("main::update_bios() | BIOS Update Complete {0}".format(bios_bin))
		print("BIOS Update Complete. Please reboot to use new BIOS.")
		logging.info(bios_update)
		logging.info("main::update_bios() | IPMI Update Complete {0}".format(bios_bin))

def download_file(url, dl_path):
	print("Downloading {0} to {1}".format(url, dl_path))
	urllib.request.urlretrieve(url, dl_path)

def extract_zip(zip_file, extract_dir):
	import zipfile
	with zipfile.ZipFile(zip_file,"r") as zipped:
    		zipped.extractall(extract_dir)

def find_bios_file(bios_bin):
	if os.path.isdir("/tmp/bios_update/{0}/UEFI".format(bios_bin)) and is_uefi_boot():
		return delegator.run("ls /tmp/bios_update/{0}/UEFI/{0}".format(bios_bin)).out
	elif os.path.isdir("/tmp/bios_update/BIOS") and not is_uefi_boot():
		return delegator.run("ls /tmp/bios_update/{0}/BIOS/{0}".format(bios_bin)).out
	else:
		return delegator.run("ls /tmp/bios_update/{0}".format(bios_bin)).out

def find_ipmi_file(ipmi_bin):
	return delegator.run("ls /tmp/ipmi_update/*.bin").out

def is_alpha_version(ver):
     try:
        return ver.encode('ascii').isalpha()
     except:
        return False

def eval_version(cur_version, new_version, ipmi=False):
		version = re.findall(r"[^\W\d_]+|\d+", cur_version)
		cur_major = int(version[0])
		cur_minor = int(version[1])
		cur_ver = float(str(cur_major) + "." + str(cur_minor))
		if ipmi == False and is_alpha_version(cur_version):
				cur_alpha = cur_version[2]
		version_new = re.findall(r"[^\W\d_]+|\d+", new_version)
		if ipmi == False and is_alpha_version(new_version):
				new_alpha = new_version[2]
		new_major = int(version_new[0])
		new_minor = int(version_new[1])
		new_ver = float(str(new_major) + "." + str(new_minor))
		if new_ver > cur_ver:
			return True
		if new_ver == cur_ver:
			if is_alpha_version(new_version):
				if is_alpha_version(old_version):
					if alpha_dict[new_alpha] > alpha_dict[cur_alpha]:
						return True
					else:
						return False
				else:
					return True #Alpha versions are higher than a non-alpha version (3.1a > 3.1)
		if new_ver < cur_ver:
			return False

def get_latest_bios(board_model):
	update_choice = None
	latest_bios_revision = None
	for link in links:
		link_board = link.split("/")[-1].split(".")[0]
		if board_model.replace("+", "_") == link_board:
			driver.get("https://www.supermicro.com{0}".format(link))
			driver.find_element_by_xpath('//a[@href="{0}"]'.format("javascript:document.biosForm.submit();")).click()
			raw = driver.find_element_by_class_name("yui-skin-sam").text.split("\n")
			for line in raw:
				if "BIOS Revision:" in line:
					latest_bios_version = line.split(":")[1].replace("R", "").strip()
			a = driver.find_element_by_partial_link_text('.zip')
			filename = a.text
			software_id = a.get_attribute("href").split("=")[-1]
			bios_dl_link = "https://www.supermicro.com/Bios/softfiles/{0}/{1}".format(software_id, filename)
			if latest_bios_version and bios_dl_link:
				return [latest_bios_version, bios_dl_link]
			else:
				print("failed to download bios information")
	if latest_bios_revision == None:
		print("Failed to find BIOS online")

def get_latest_ipmi(board_model):
	for link in links:
		link_board = link.split("/")[-1].split(".")[0]
		if board_model.replace("+", "_") == link_board:
				driver.get("https://www.supermicro.com{0}".format(link))
				driver.find_element_by_xpath('//a[@href="{0}"]'.format("javascript:document.IPMIForm.submit();")).click()
				raw = driver.find_element_by_class_name("yui-skin-sam").text.split("\n")
				for line in raw:
					if "Firmware Revision:" in line:
						latest_ipmi_version = line.split(":")[1].strip(" R")
				a = driver.find_element_by_partial_link_text('.zip')
				filename = a.text
				software_id = a.get_attribute("href").split("=")[-1]
				ipmi_dl_link = "https://www.supermicro.com/Bios/softfiles/{0}/{1}".format(software_id, filename)
				return [latest_ipmi_version, ipmi_dl_link]

def main():
	board_model = get_board_model()
	bios_version = get_current_bios()
	bios_dl = get_latest_bios(board_model)
	ipmi_version = get_current_ipmi()
	ipmi_dl = get_latest_ipmi(board_model)
	sys_headers = ['FW', 'CURRENT', 'LATEST']
	cli_ui.info_section(cli_ui.green, cli_ui.bold, "SMC UPDATER")
	board_header = ['BOARD MODEL']
	board_data = [[(cli_ui.bold, board_model)]]
	cli_ui.info_table(board_data, headers=board_header)
	print()
	sys_data = [
		[(cli_ui.bold, "BIOS"), (cli_ui.bold, bios_version), (cli_ui.bold, bios_dl[0])],
		[(cli_ui.bold, "IPMI"), (cli_ui.bold, ipmi_version), (cli_ui.bold, ipmi_dl[0])]
	]
	cli_ui.info_table(sys_data, headers=sys_headers)
	print()
	if eval_version(bios_version, bios_dl[0]):
		update_choice = None
		while update_choice == None or update_choice == 'y':
			bios_old = True
			if manual_run == True:
				update_choice = cli_ui.ask_string("BIOS is out of date. Would you like to update now? [y/n]")
				if update_choice != 'y':
					continue
			bin_file = bios_dl[1].split("/")[-1]
			bin_name = bin_file.split("_")[0]
			bin_ver = bin_file.split(".")[0].split("_")[-1]
			bin_raw = bin_file.split(".")[0]
			bin_ex = "{0}.{1}".format(bin_name, bin_ver)
			download_file(bios_dl[1], '/tmp/{0}'.format(bios_dl[1].split("/")[-1]))
			extract_zip("/tmp/{0}".format(bin_file), "/tmp/bios_update/")
			bios_file_path = find_bios_file(bin_ex)
			update_bios(bios_file_path)
			break
	else:
		print("BIOS is up-to-date.")
	# 	logging.info("main(): Website version is newer, updating BIOS...")
	if eval_version(ipmi_version, ipmi_dl[0], ipmi=True):
		update_choice = None
		while update_choice == None or update_choice == 'y':
			ipmi_old = True
			if manual_run == True:
				update_choice = cli_ui.ask_string("IPMI is out of date. Would you like to update now? [y/n]")
			logging.info("main(): Webiste version is newer, updating IPMI...")
			bin_file = ipmi_dl[1].split("/")[-1]
			bin_name = bin_file.split(".")[0]
			bin_ex = "{0}.{1}".format(bin_name, 'bin')
			download_file(ipmi_dl[1], '/tmp/{0}'.format(ipmi_dl[1].split("/")[-1]))
			extract_zip("/tmp/{0}".format(bin_file), "/tmp/ipmi_update/")
			ipmi_file_path = "/tmp/ipmi_update/{0}.bin".format(bin_name)
			update_ipmi(ipmi_file_path)
			break
	else:
		print("IPMI is up-to-date.")
	print("\nExiting...")

if __name__ == "__main__":
	if not delegator.run("which dmidecode").out:
		print("Fatal Error: dmidecode not detected.")
		exit()
	#logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')
	#binary = FirefoxBinary('./geckodriver')
	options = Options()
	options.headless = True

	driver = webdriver.Firefox(options=options)
	#File created with "for i in `curl -s https://www.supermicro.com/products/motherboard/| grep quaternaryNavItem|awk -F ' ' {'print $2'}| sed 's/href=\"//'|sed 's/\"//'|grep -v 'Global_SKU'`; do curl -s https://www.supermicro.com/${i} | grep prodLink| awk -F '<a href="' {'print $2'}| awk -F 'class=' {'print $1'}|sed 's/\"//'|grep -v Global_SKU >> smc_board_links.txt;done"
	with open("smc_board_links.txt") as f:
		links = f.readlines()
	main()
