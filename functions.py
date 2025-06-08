import re
from prettytable import PrettyTable


def func_check_global_export(
    configuration: str, baseline_config_global: dict, log_failed_only=False
):
    """Function to check if specific commands are in the content.
    Args:
        content (str): Configuration content to check
        baseline_config (dict): dictionary with commands to check in the content
        log_failed_only (bool, optional): Notice just FAILed tests. Defaults to False.

    Returns:
        dict : Dictionary with global commands and their results
    """
    dict_global = {}

    for global_command in baseline_config_global:
        global_pattern = r"(?m)^" + global_command

        result = re.search(global_pattern, configuration)
        if result:
            if not log_failed_only:
                dict_global[global_command] = {"RESULT": "PASS"}
        else:
            dict_global[global_command] = {"RESULT": "FAIL"}

    return dict_global


def func_check_interface_export(content, baseline_config, log_failed_only=False):
    ###########################################
    # function to parse interface commands
    ###########################################

    # or is not working as it should work
    if ("interface_commands" in baseline_config) or (
        "trunk_interface_commands" in baseline_config
    ):

        # defining regex search pattern
        pattern_interface_block = r"(?m)^interface[^!]*"

        # get all interface config blocks
        interfaces = re.findall(pattern_interface_block, content, re.DOTALL)

        dict_interfaces = {}
        dict_interfaces_excluded = {}
        dict_interfaces_trunk = {}

        # loop through interface blocks
        for interface in interfaces:
            # get interface name via regex

            interface_name = get_interface_name(interface)
            dict_interface = {}
            dict_command = {}

            exclude_interface = ("interface_exclude" in baseline_config) and (
                is_interface_excluded(
                    baseline_config["interface_exclude"], interface_name
                )
            )

            # check if interface is trunk and set flag
            trunk_mode_interface = re.search("switchport mode trunk", interface)
            if trunk_mode_interface:
                trunk_interface = True
            else:
                trunk_interface = False

            # this is where the magic happens
            if exclude_interface:
                dict_interfaces_excluded[interface_name[10:]] = {}
                # break

            elif trunk_interface is True:
                for command in baseline_config["trunk_interface_commands"]:
                    # check if command is there
                    result = re.search(command, interface)
                    if result:
                        if log_failed_only is False:
                            dict_command[command] = {"RESULT": "PASS"}
                    else:
                        dict_command[command] = {"RESULT": "FAIL"}
                dict_interface["TESTS"] = dict_command
                dict_interface["RAW_DATA"] = interface
                dict_interfaces_trunk[interface_name[10:]] = dict_interface

            else:
                if "interface_commands" in baseline_config:
                    for command in baseline_config["interface_commands"]:

                        # check if command is there
                        result = re.search(command, interface)
                        if result:
                            if log_failed_only is False:
                                dict_command[command] = {"RESULT": "PASS"}
                        else:
                            dict_command[command] = {"RESULT": "FAIL"}

                    # entry in json for each interface
                    dict_interface["TESTS"] = dict_command
                    dict_interface["RAW_DATA"] = interface
                    dict_interfaces[interface_name[10:]] = dict_interface

        dict_type = {
            "ACCESS": dict_interfaces,
            "TRUNK": dict_interfaces_trunk,
            "EXCLUDED": dict_interfaces_excluded,
        }
    return dict_type


def is_interface_excluded(excluded_interfaces, interface_name):
    exclude_interface = False
    for exclude in excluded_interfaces:
        if re.findall(exclude, interface_name):
            exclude_interface = True
    return exclude_interface


def get_interface_name(interface):
    interface_name = re.match("interface.*", interface)
    interface_name = interface_name.group(0) if interface_name else "interface unknown"

    return interface_name


def func_check_data(device_configuration, baseline_config, log_failed_only=False):

    dict_data = {}

    if "global_commands" in baseline_config:
        global_dict = func_check_global_export(
            device_configuration, baseline_config["global_commands"], log_failed_only
        )
    else:
        global_dict = {}
    # print(global_dict)

    interface_dict = func_check_interface_export(
        device_configuration, baseline_config, log_failed_only
    )
    # print(interface_dict)

    dict_data["GLOBAL"] = global_dict
    dict_data["INTERFACES"] = interface_dict

    return dict_data


def func_check_show(show_command_output, baseline_config, log_failed_only=False):

    result_show = {}

    if "show_commands" in baseline_config:
        for show_commands in baseline_config["show_commands"]:

            result_show[show_commands] = {}
            result_show[show_commands]["TESTS"] = {}

            for test in baseline_config["show_commands"][show_commands]:
                result = re.findall(test, show_command_output[show_commands], re.DOTALL)
                if result:
                    if not log_failed_only:
                        result_show[show_commands]["TESTS"][test] = {"Result": "PASS"}
                else:
                    result_show[show_commands]["TESTS"][test] = {"Result": "FAIL"}

            result_show[show_commands]["RAW_DATA"] = show_command_output[show_commands]

    return result_show


def func_check_device_info(device_info):
    info = {}

    # check model number
    result = re.findall("Model Number.*", device_info)

    if result:
        model = result[0]
        index = model.rfind(":") + 2
        info["MODEL"] = model[index:]
    else:
        info["MODEL"] = "UNKNOWN"

    return info


def func_print_database(data, options, a_logger):

    # print file or device
    for section, section_data in data.items():
        print("############################")
        print("#### " + section)
        for device, device_data in section_data.items():
            a_logger.info("\n############################")
            a_logger.info("#### " + device)

            if device_data == "ERROR":
                a_logger.info("############################")
                a_logger.info("Device was offline or other error occured !")
            else:
                # TODO: this is failing for file based config:
                # a_logger.info("#### Type: " + device_data["DEVICE_INFO"]["MODEL"])
                a_logger.info("############################")
                print(create_list_table(device_data))
            a_logger.info("\n")


def create_list_table(device_data):

    def list_of_interface_data(interface_data, interface_name, type="TRUNK"):
        list_of_rows = []
        for section, section_items in interface_data[interface_name].items():
            if section == "TESTS":
                for commands in section_items:
                    list_of_rows.append(
                        [
                            interface_name,
                            commands,
                            type,
                            section_items[commands]["RESULT"],
                        ]
                    )
        return list_of_rows

    def global_rows(global_data):
        rows = []
        for section, commands in global_data.items():
            for command, result in commands.items():
                rows.append(["GLOBAL", section, "GLOBAL", result])
        if rows:
            rows.append(["", "", "", ""])
        return rows

    def interface_rows(interface_data):
        rows = []
        for intf_type, intf_dict in interface_data.items():
            if intf_type == "EXCLUDED":
                rows.extend([[name, "", "", "EXCLUDED"] for name in intf_dict])
            else:
                for name in intf_dict:
                    rows.extend(list_of_interface_data(intf_dict, name, intf_type))
        if rows:
            rows.append(["", "", "", ""])
        return rows

    def show_command_rows(show_data):
        rows = []
        for show_cmd, show_cmd_data in show_data.items():
            tests = show_cmd_data.get("TESTS")
            if tests:
                for test, result in tests.items():
                    rows.append([show_cmd, test, "SHOW", result["Result"]])
            else:
                raise ValueError(
                    "Unknown section in SHOW_COMMANDS: ", show_cmd_data.keys()
                )
        return rows

    list_of_rows = []

    if "GLOBAL" in device_data:
        list_of_rows.extend(global_rows(device_data["GLOBAL"]))

    if "INTERFACES" in device_data:
        list_of_rows.extend(interface_rows(device_data["INTERFACES"]))

    if "SHOW_COMMANDS" in device_data:
        list_of_rows.extend(show_command_rows(device_data["SHOW_COMMANDS"]))

    table = PrettyTable(["scope", "command", "type", "result"])
    for row in list_of_rows:
        table.add_row(row)
    return table


def banner(a_logger):
    a_logger.info("############################################")
    a_logger.info("### config checker v0.4                 ####")
    a_logger.info("### Tomas Fidler                        ####")
    a_logger.info("### github.com/fidlertomas/config-checker ##")
    a_logger.info("############forked from ####################")
    a_logger.info("### config checker v0.3                 ####")
    a_logger.info("### Paul Freitag                        ####")
    a_logger.info("### github.com/catachan/config-checker  ####")
    a_logger.info("############################################\n")
