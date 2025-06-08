import getpass
import functions
import os
import yaml
import json
import sys
import argparse
from netmiko import ConnectHandler
import logging


def parse_arguments():
    ###########################################
    # function to get command line arguments
    ###########################################

    parser = argparse.ArgumentParser(description="Config Checker Arguments")
    parser.add_argument("-d", "--directory", help="Directory for offline mode")
    parser.add_argument(
        "-b", "--baseline_yaml", required=True, help="Baseline YAML file (mandatory)"
    )
    parser.add_argument(
        "-c", "--connection_yaml", help="Connection YAML file for online mode"
    )
    parser.add_argument(
        "-f", "--failed_only", action="store_true", help="Show only failed checks"
    )
    parser.add_argument("-r", "--reporting", help="json file for saving report")
    parser.add_argument(
        "-l",
        "--logging",
        default="config-checker.log",
        help="Logging file (default: config-checker.log)",
    )
    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="Print results to console",
    )

    args = parser.parse_args()

    options = vars(args)

    # Check for required mode: either directory or connection_yaml must be provided
    if not options.get("directory") and not options.get("connection_yaml"):
        parser.error("-d (offline mode) or -c (online mode) is mandatory")

    return options


def setup_logging(log_file=None):

    a_logger = logging.getLogger()
    a_logger.setLevel(logging.INFO)
    stdout_handler = logging.StreamHandler(sys.stdout)
    a_logger.addHandler(stdout_handler)

    if log_file:
        output_file_handler = logging.FileHandler(log_file)
        a_logger.addHandler(output_file_handler)

    functions.banner(a_logger)
    return a_logger


def export_dat_to_json(filename, data):

    with open(filename, "w") as outfile:
        json.dump(data, outfile)


def verify_devices_online(
    options_connection_yaml_filename, a_logger, baseline_config, log_only_failed=False
):
    with open(options_connection_yaml_filename) as device_file:
        device_dict = yaml.full_load(device_file)

    update_global_parameters(device_dict)

    data = {}

    # loop through devices
    for device in device_dict["device"]:
        show_command_output = {}
        device_parameters = device_dict["device"][device]
        # check if device is disabled
        if device_parameters.get("disable", False):
            a_logger.info(
                "Skipping device " + device + " (" + device_parameters["ip"] + ") ..."
            )
            continue

        a_logger.info(
            "Connecting to " + device + " (" + device_parameters["ip"] + ") ..."
        )

        try:
            con_param = prepare_connection_parameters(
                device_parameters, device_dict.get("global", None)
            )
            con_device = ConnectHandler(**con_param)
            con_device.enable()

            content = con_device.send_command("show running-config")

            if "show_commands" in baseline_config:
                for show_commands in baseline_config["show_commands"]:
                    show_command_output[show_commands] = con_device.send_command(
                        "show " + show_commands
                    )

            device_info = con_device.send_command("show version")

            con_device.disconnect()

            # check and print data
            data[device] = functions.func_check_data(
                content, baseline_config, log_only_failed
            )
            data[device]["SHOW_COMMANDS"] = functions.func_check_show(
                show_command_output, baseline_config, log_only_failed
            )
            data[device]["DEVICE_INFO"] = functions.func_check_device_info(device_info)

            a_logger.info("     Done ...")

        except Exception as e:
            a_logger.error(
                "     Error while connecting to device " + device + ": " + str(e)
            )
            data[device] = "ERROR"

    return data


def prepare_connection_parameters(device_parameters, global_parameters):
    return {
        "device_type": device_parameters["device_type"],
        "ip": device_parameters["ip"],
        "username": device_parameters.get(
            "username",
            (global_parameters.get("username", None) if global_parameters else None),
        ),
        "password": device_parameters.get(
            "password",
            (global_parameters.get("password", None) if global_parameters else None),
        ),
        "secret": device_parameters["secret"],
    }


def update_global_parameters(devices):
    if "global" in devices:
        if devices["global"].get("ask_for_username", False):
            devices["global"]["username"] = input("Enter global username: ")
        if devices["global"].get("ask_for_password", False):
            devices["global"]["password"] = getpass.getpass("Enter global password: ")


def verify_configs_in_directory(directory, baseline_config, log_only_failed=False):
    data = {}
    # get file list in directory
    config_list = os.listdir(directory)

    # loop through config files
    for config in config_list:
        file = directory + "\\" + config

        # open file and read content
        with open(file) as f_obj:
            content = f_obj.read()

            # check and print data
            data[config] = functions.func_check_data(
                content, baseline_config, log_only_failed
            )
    return data


def main():
    # get command line arguments
    options = parse_arguments()

    a_logger = setup_logging(options["logging"])

    # load yaml file with baseline config
    with open(options["baseline_yaml"]) as baseline_yaml_file:
        baseline_config = yaml.full_load(baseline_yaml_file)

    data = {}

    if options["directory"]:
        # execute directory/offline mode
        data["FILE"] = verify_configs_in_directory(
            options["directory"], baseline_config, options["failed_only"]
        )

    elif "connection_yaml" in options:
        # execute online/ssh mode
        data["DEVICE"] = verify_devices_online(
            options["connection_yaml"],
            a_logger,
            baseline_config,
            log_only_failed=options["failed_only"],
        )

    else:
        a_logger.info("Unknown Error --> you should never see this")

    # export json data if possible
    if options["reporting"]:
        export_dat_to_json(options["reporting"], data)

    # print data
    if options.get("print", True):
        functions.func_print_database(data, options, a_logger)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nKeyboard Interrupt detected. Exiting ...")
        sys.exit(0)
    except Exception as e:
        print("An error occurred: ", e)
        raise e
