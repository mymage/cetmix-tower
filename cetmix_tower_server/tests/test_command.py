from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import Form

from .common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        # Save variable values for Server 1
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "test-odoo-1"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "/opt/tower"
            f.save()

        # Secret key
        self.secret_folder_key = self.Key.create(
            {
                "name": "Folder",
                "reference": "FOLDER",
                "secret_value": "secretFolder",
                "key_type": "s",
            }
        )
        self.secret_python_key = self.Key.create(
            {
                "name": "python",
                "reference": "PYTHON",
                "secret_value": "secretPythonCode",
                "key_type": "s",
            }
        )

        # secret value as multi line string
        self.python_ssh_key = self.Key.create(
            {
                "name": "Test Python SSH Key",
                "reference": "test_python_ssh_key",
                "key_type": "k",
                "secret_value": """
                Python
                much
                key
                """,
            }
        )

        self.secret_test_rsa_key = self.Key.create(
            {
                "name": "test rsa",
                "reference": "test_rsa",
                "secret_value": """-----BEGIN RSA PRIVATE KEY-----
MIIBOgIBAAJBAKj34GkxFhD90vcNLYLInFEX6Ppy1tPf9Cnzj4p4WGeKLs1Pt8Qu
KUpRKfFLfRYC9AIKjbJTWit+CqvjWYzvQwECAwEAAQJAIJLixBy2qpFoS4DSmoEm
o3qGy0t6z09AIJtH+5OeRV1be+N4cDYJKffGzDa88vQENZiRm0GRq6a+HPGQMd2k
TQIhAKMSvzIBnni7ot/OSie2TmJLY4SwTQAevXysE2RbFDYdAiEBCUEaRQnMnbp7
9mxDXDf6AU0cN/RPBjb9qSHDcWZHGzUCIG2Es59z8ugGrDY+pxLQnwfotadxd+Uy
v/Ow5T0q5gIJAiEAyS4RaI9YG8EWx/2w0T67ZUVAw8eOMB6BIUg0Xcu+3okCIBOs
/5OiPgoTdSy7bcF9IGpSE8ZgGKzgYQVZeN97YE00
-----END RSA PRIVATE KEY----- """,
                "key_type": "s",
            }
        )
        # Command
        self.command_create_new_command = self.Command.create(
            {
                "name": "Create new command",
                "action": "python_code",
                "code": """
server_name = {{ tower.server.name }}
if server_name and #!cxtower.secret.FOLDER!# == "secretFolder":
    command = env["cx.tower.command"].create({"name": {{ test_path_ }}})
    COMMAND_RESULT = {"exit_code": 0, "message": "New command was created"}
else:
    COMMAND_RESULT = {"exit_code": -1, "message": "error"}
    """,
            }
        )

        self.command_python_command_1 = self.Command.create(
            {
                "name": "Python command with secret #1",
                "action": "python_code",
                "code": """
COMMAND_RESULT = {
    "exit_code": 0,
    "message": #!cxtower.secret.PYTHON!#,
}
    """,
            }
        )

        self.command_python_command_2 = self.Command.create(
            {
                "name": "Python command with secret #2",
                "action": "python_code",
                "code": """
COMMAND_RESULT = {
    "exit_code": 0,
    "message": 'We use #!cxtower.secret.PYTHON!#' ,
}
    """,
            }
        )

        self.command_python_command_3 = self.Command.create(
            {
                "name": "Python command with secret #3",
                "action": "python_code",
                "code": """
COMMAND_RESULT = {
    "exit_code": 0,
    "message": ""#!cxtower.secret.test_rsa!#"" ,
}
    """,
            }
        )

        self.command_python_command_4 = self.Command.create(
            {
                "name": "Python command with secret #4",
                "action": "python_code",
                "code": """
top_secret = #!cxtower.secret.test_python_ssh_key!#
COMMAND_RESULT = {
    "exit_code": 0,
    "message": top_secret ,
}
    """,
            }
        )

    def test_ssh_command_prepare_method_without_path(self):
        """Test ssh command preparation in different modes without path"""

        server = self.server_test_1

        single_command = "ls -a /tmp"
        multiple_commands = "ls -a /tmp && mkdir /tmp/test"

        sudo_mode = "p"

        # Prepare single command for sudo with password
        cmd = server._prepare_ssh_command(single_command, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [f"{self.sudo_prefix} {single_command}"],
            msg=(
                "Single command for sudo with password should be "
                "equal to list with the original command"
                "as an only element"
            ),
        )

        # Prepare multiple commands for sudo with password
        cmd = server._prepare_ssh_command(multiple_commands, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [
                f"{self.sudo_prefix} ls -a /tmp",
                f"{self.sudo_prefix} mkdir /tmp/test",
            ],
            msg=(
                "Multiple commands with sudo with password should be "
                "a list of separated commands from original line"
            ),
        )

        sudo_mode = "n"

        # Prepare single command for sudo without password
        cmd = server._prepare_ssh_command(single_command, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"{self.sudo_prefix} {single_command}",
            msg=(
                "Single command with sudo without password should be "
                f'equal to the original command prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare multiple commands for sudo without password
        cmd = server._prepare_ssh_command(multiple_commands, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"{self.sudo_prefix} ls -a /tmp && {self.sudo_prefix} mkdir /tmp/test",
            msg=(
                "Multiple commands with sudo with password should be "
                "a re-joined string from list of separated original "
                f'each prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare single command without sudo
        cmd = server._prepare_ssh_command(single_command)
        self.assertEqual(
            cmd,
            single_command,
            msg=(
                "Single command without sudo should be "
                "equal to the original command "
            ),
        )

        # Prepare multiple without sudo
        cmd = server._prepare_ssh_command(multiple_commands)
        self.assertEqual(
            cmd,
            multiple_commands,
            msg=(
                "Multiple commands without sudo should be "
                "equal to the original line of commands"
            ),
        )

    def test_ssh_command_prepare_method_with_path(self):
        """Test command preparation in different modes without path"""

        server = self.server_test_1

        single_command = "ls -a /tmp"
        multiple_commands = "ls -a /tmp && mkdir /tmp/test"
        path = "/home/doge"

        sudo_mode = "p"

        # Prepare single command for sudo with password
        cmd = server._prepare_ssh_command(single_command, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [f"cd {path}", f"{self.sudo_prefix} {single_command}"],
            msg=(
                "Single command for sudo with password should be "
                "equal to list of two elements:"
                " change directory and original command"
            ),
        )

        # Prepare multiple commands for sudo with password
        cmd = server._prepare_ssh_command(multiple_commands, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [
                f"cd {path}",
                f"{self.sudo_prefix} ls -a /tmp",
                f"{self.sudo_prefix} mkdir /tmp/test",
            ],
            msg=(
                "Multiple commands with sudo with password should be "
                "a list of separated commands from original line"
            ),
        )

        sudo_mode = "n"

        # Prepare single command for sudo without password
        cmd = server._prepare_ssh_command(single_command, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"cd {path} && {self.sudo_prefix} {single_command}",
            msg=(
                "Single command with sudo without password should be "
                f'equal to the original command prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare multiple commands for sudo without password
        cmd = server._prepare_ssh_command(multiple_commands, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"cd {path} && {self.sudo_prefix} ls -a /tmp && {self.sudo_prefix} mkdir /tmp/test",  # noqa
            msg=(
                "Multiple commands with sudo with password should be "
                "a re-joined string from list of separated original "
                f'each prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare single command without sudo
        cmd = server._prepare_ssh_command(single_command, path=path)
        self.assertEqual(
            cmd,
            f"cd {path} && {single_command}",
            msg=(
                "Single command for without sudo should be "
                "equal to the the original command"
                "with 'cd {{ path }} && ' prefix"
            ),
        )

        # Prepare multiple commands without sudo
        cmd = server._prepare_ssh_command(multiple_commands, path=path)
        self.assertEqual(
            cmd,
            f"cd {path} && {multiple_commands}",  # noqa
            msg=(
                "Multiple commands without sudo should be "
                "original command with 'change directory' command prepended"
            ),
        )

    def test_server_render_command(self):
        """Test rendering command using `_render_command` method
        of cx.tower.server
        """

        # -- 1 --
        # Test with default path
        rendered_command = self.server_test_1._render_command(self.command_create_dir)
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 2 --
        # Test with custom path
        rendered_command = self.server_test_1._render_command(
            self.command_create_dir, path="/such/much/path"
        )
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"
        rendered_path_expected = "/such/much/path"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 3 --
        # Set variable_path to None and check again
        variable_value_path = self.server_test_1.variable_value_ids.filtered(
            lambda var_val: var_val.variable_id.id == self.variable_path.id
        )
        variable_value_path.value_char = None
        rendered_command = self.server_test_1._render_command(self.command_create_dir)
        rendered_code_expected = "cd False && mkdir test-odoo-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 4 --
        # Set both path and code to None
        self.write_and_invalidate(
            self.command_create_dir, **{"code": None, "path": None}
        )
        rendered_command = self.server_test_1._render_command(self.command_create_dir)

        self.assertFalse(
            rendered_command["rendered_code"], "Rendered code doesn't match"
        )
        self.assertFalse(
            rendered_command["rendered_path"], "Rendered path doesn't match"
        )

    def test_render_code_generic(self):
        """Test generic (aka ssh) code template direct rendering"""

        # Only 'test_path_' must be rendered
        args = {"test_path_": "/tmp", "test_os": "debian"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        rendered_code_expected = "cd /tmp && mkdir "
        self.assertEqual(
            rendered_code,
            rendered_code_expected,
            msg=f"Must be rendered as '{rendered_code_expected}'",
        )

        # 'test_path_' and 'dir' must be rendered
        args = {"test_path_": "/tmp", "os": "debian", "test_dir": "odoo"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        self.assertEqual(
            rendered_code,
            "cd /tmp && mkdir odoo",
            msg="Must be rendered as 'cd /tmp && mkdir odoo'",
        )

    def test_execute_command_with_variables(self):
        """Test code execution using command log records"""

        x = 1  # Used to distinguish labels

        # Check with all available "sudo" option
        for sudo in [False, "n", "p"]:
            # Add label to track command log
            command_label = f"Test Command {x}"
            custom_values = {"log": {"label": command_label}}

            # Execute command for Server 1
            self.server_test_1.execute_command(
                self.command_create_dir, sudo=sudo, **custom_values
            )

            # Expected rendered command code
            rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"

            # Get command log
            log_record = self.CommandLog.search([("label", "=", command_label)])

            # Check log values
            self.assertEqual(len(log_record), 1, msg="Must be a single log record")
            self.assertEqual(
                log_record.server_id.id,
                self.server_test_1.id,
                msg="Record must belong to Test 1",
            )
            self.assertEqual(
                log_record.command_id.id,
                self.command_create_dir.id,
                msg="Record must belong to command 'Create dir'",
            )
            self.assertEqual(
                log_record.code,
                rendered_code_expected,
                msg=f"Rendered code must be '{rendered_code_expected}'",
            )
            self.assertEqual(
                log_record.command_status, 0, msg="Command status must be equal to 0"
            )
            self.assertEqual(
                log_record.use_sudo,
                sudo,
                msg="'sudo' param in log doesn't match the command one",
            )

            # Increment label counter
            x += 1

    def test_execute_command_with_keys(self):
        """Test command with keys in code"""

        # Command
        code = "cd {{ test_path_ }} && mkdir #!cxtower.secret.FOLDER!#"
        command_with_keys = self.Command.create(
            {"name": "Command with keys", "code": code}
        )

        # Parse command with key parser to ensure key is parsed correctly
        code_parsed_expected = "cd {{ test_path_ }} && mkdir secretFolder"
        code_parsed = self.Key._parse_code(code)
        self.assertEqual(
            code_parsed,
            code_parsed_expected,
            msg="Parsed code doesn't match expected one",
        )

        # Add label to track command log
        command_label = "Test Command with keys"
        custom_values = {"log": {"label": command_label}}

        # Execute command for Server 1
        self.server_test_1.execute_command(command_with_keys, **custom_values)

        # Expected rendered command code
        rendered_code_expected = "cd /opt/tower && mkdir #!cxtower.secret.FOLDER!#"

        # Get command log
        log_record = self.CommandLog.search([("label", "=", command_label)])

        # Check log values
        self.assertEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            log_record.server_id.id,
            self.server_test_1.id,
            msg=("Record must belong %s", self.server_test_1.name),
        )
        self.assertEqual(
            log_record.command_id.id,
            command_with_keys.id,
            msg=("Record must belong to command %s", command_with_keys.name),
        )
        self.assertEqual(
            log_record.code,
            rendered_code_expected,
            msg="Rendered code must be '{}'".format(rendered_code_expected),
        )
        self.assertEqual(
            log_record.command_status, 0, msg="Command status must be equal to 0"
        )

    def test_user_access_rule(self):
        """Test user access rule"""
        # Create the test command
        test_command = self.Command.create({"name": "Test command"})

        # Ensure that defaulf command access_level is equal to 2
        self.assertEqual(test_command.access_level, "2")
        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot access the command
        test_command_1_as_bob = test_command.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            command_name = test_command_1_as_bob.name
        test_command.write({"access_level": "1"})
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Ensure that user can access the command
        command_name = test_command_1_as_bob.name
        self.assertEqual(command_name, "Test command", msg="Must return 'Test command'")

        # Check that user with "cetmix_tower_server.group_user" can execute ssh command
        test_command.write(
            {
                "code": "ls -l",
            }
        )
        self.server_test_1.with_user(self.user_bob).execute_command(
            test_command,
        )

        # Add user to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Create a new command with access_level 1
        new_command = self.Command.with_user(self.user_bob).create(
            {"name": "New Test Command", "access_level": "1"}
        )
        self.assertEqual(new_command.access_level, "1")
        # Try to elevate the access_level of new_command to 2
        new_command.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(new_command.access_level, "2")

        # Ensure that manager user cannot see commands with access_level 3

        restricted_command = self.Command.create(
            {"name": "Restricted Command", "access_level": "3"}
        )

        user_bob_records = self.Command.with_user(self.user_bob).search([])
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertFalse(user_bob_records_access_level_3, "Must return 0 records")
        # Add user to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        # Ensure that root user can see commands with access_level 3
        user_bob_records = self.Command.with_user(self.user_bob).search([])
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertTrue(user_bob_records_access_level_3, "Must not be empty")
        self.assertIn(
            restricted_command,
            user_bob_records_access_level_3,
            "Restricted command must be in the list",
        )

        # Try to demote the access_level of new_command to 2
        restricted_command.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(restricted_command.access_level, "2")
        # Checking the case that may require clearing the cache:
        # Create a command with "Manager" access level.
        cc_command = self.Command.create({"name": "CC Command", "access_level": "2"})

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Check command list with "Tower-User" user. User cannot see this command.
        with self.assertRaises(AccessError):
            command_name = cc_command.with_user(self.user_bob).name
        # Change the command access level to "User".
        cc_command.write({"access_level": "1"})

        command_name = cc_command.with_user(self.user_bob).name
        self.assertEqual(command_name, "CC Command", msg="Must return 'CC command'")
        # Assign cc_command.server_ids to self.server_test_1
        cc_command.write({"server_ids": [(6, 0, [self.server_test_1.id])]})
        # Ensure Bob can't access cc_command if he is not a follower
        #  of self.server_test_1
        with self.assertRaises(AccessError):
            cc_command.with_user(self.user_bob).read([])
        # Add Bob to the manager group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")

        # Ensure Bob as manager still can't access cc_command if he is not
        # a follower of self.server_test_1
        with self.assertRaises(AccessError):
            cc_command.with_user(self.user_bob).read([])

        # Subscribe Bob to self.server_test_1
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])

        # Ensure Bob can now access cc_command as a follower of self.server_test_1
        cc_command_read_result = cc_command.with_user(self.user_bob).read([])
        self.assertEqual(
            cc_command_read_result[0]["name"],
            cc_command.name,
            msg="Command name should be same",
        )

        # Remove Bob from manager group
        self.remove_from_group(self.user_bob, ["cetmix_tower_server.group_manager"])

        # Ensure Bob retains access to cc_command because he is a follower
        cc_command_read_result = cc_command.with_user(self.user_bob).read([])
        self.assertEqual(
            cc_command_read_result[0]["name"],
            cc_command.name,
            msg="Command name should be same",
        )

    def test_parse_ssh_command_result(self):
        """Test ssh command result parsing"""

        # -------------------------------------------------------
        # Case 1: regular command execution result with no error
        # We are testing secret value placeholder here
        # -------------------------------------------------------
        status = 0
        response = ["Such much", f"Doge like SSH {self.Key.SECRET_VALUE_SPOILER}"]
        error = []

        ssh_command_result = self.Server._parse_command_results(
            status, response, error, key_values=[f"{self.secret_2.secret_value}"]
        )

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            result_status,
            "Status in result must be the same as the initial one",
        )
        self.assertEqual(
            result_response,
            f"Such muchDoge like SSH {self.Key.SECRET_VALUE_SPOILER}",
            "Response in result doesn't match expected",
        )
        self.assertIsNone(result_error, "Error in response must be set to None")

        # -------------------------------------------------------
        # Case 2: no response but an error
        # -------------------------------------------------------
        status = 1
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            result_status,
            "Status in result must be the same as the initial one",
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 3: several codes all 0, no response but an error
        # -------------------------------------------------------
        status = [0, 0, 0]
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status, 0, "Status in result doesn't match expected one"
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 4: codes [0,1,0,4,0], no response but an error
        # -------------------------------------------------------
        status = [0, 1, 0, 4, 0]
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status, 4, "Status in result doesn't match expected one"
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 5: regular command execution result with no error
        # However the command result is saved in the "error" value.
        # For example this happens in 'docker build'.
        # -------------------------------------------------------
        status = 0
        error = ["Such much", f"Doge like SSH {self.Key.SECRET_VALUE_SPOILER}"]
        response = []

        ssh_command_result = self.Server._parse_command_results(
            status, response, error, key_values=[f"{self.secret_2.secret_value}"]
        )

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            result_status,
            "Status in result must be the same as the initial one",
        )
        self.assertEqual(
            result_error,
            f"Such muchDoge like SSH {self.Key.SECRET_VALUE_SPOILER}",
            "Response in result doesn't match expected",
        )
        self.assertIsNone(result_response, "Error in response must be set to None")

    def test_tower_command_action_file_using_template(self):
        """
        Test action file using template for tower source
        """
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.upload_file",
            return_value="ok",
        ):
            self.server_test_1.execute_command(
                self.command_create_file_with_template_tower_source
            )

        log_text_create_success = "File created and uploaded successfully"
        log_text_file_exists = "An error occurred: File already exists on server."

        # Get command log
        log_record = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_tower_source.id,
                ),
                ("command_response", "=", log_text_create_success),
            ]
        )

        self.assertEqual(len(log_record), 1, msg="Must be a single log record")

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.upload_file",
            return_value="ok",
        ):
            self.server_test_1.execute_command(
                self.command_create_file_with_template_tower_source
            )

        log_record_2 = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_tower_source.id,
                ),
                ("command_error", "=", log_text_file_exists),
            ]
        )

        self.assertEqual(len(log_record_2), 1, msg="Must be a single log record")

    def test_server_command_action_file_using_template(self):
        """
        Test action file using template for server source
        """
        self.assertFalse(self.template_file_server.file_ids)

        def download_file(this, remote_path):
            return b"Hello, world!"

        cx_tower_server_obj = self.registry["cx.tower.server"]

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.server_test_1.execute_command(
                self.command_create_file_with_template_server_source
            )

        log_text_create_success = "File created and uploaded successfully"
        log_text_file_exists = "An error occurred: File already exists on server."

        # Get command log
        log_record = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_server_source.id,
                ),
                ("command_response", "=", log_text_create_success),
            ]
        )

        self.assertEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            len(self.template_file_server.file_ids), 1, msg="Must be one file!"
        )
        self.assertEqual(
            self.template_file_server.file_ids.source,
            "server",
            msg="The File source must be 'server'",
        )

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.server_test_1.execute_command(
                self.command_create_file_with_template_server_source
            )

        log_record_2 = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_server_source.id,
                ),
                ("command_error", "=", log_text_file_exists),
            ]
        )

        self.assertEqual(len(log_record_2), 1, msg="Must be a single log record")

    def test_execute_command_no_log(self):
        """Execute command without creating a log record.
        Such commands return execution result directly.
        """
        # Add label to track command log
        command_label = "Test Command with keys"
        custom_values = {"log": {"label": command_label}}

        # Execute command for Server 1
        command_result = self.server_test_1.with_context(no_log=True).execute_command(
            self.command_create_dir, **custom_values
        )
        self.assertEqual(
            command_result["status"], 0, "Command status doesn't match expected one"
        )
        self.assertEqual(
            command_result["response"],
            "ok",
            "Command response doesn't match expected one",
        )
        self.assertIsNone(
            command_result["error"], "Command error doesn't match expected one"
        )

    # ---------------------
    # *********************
    #   Python commands
    # *********************
    # ---------------------

    def test_render_code_python(self):
        """Test Python code template direct rendering"""

        rendered_command = self.server_test_1._render_command(
            self.command_create_new_command
        )

        # Note: this is rendered as for Server Test 1
        rendered_code_pythonic = f"""
server_name = "{self.server_test_1.name}"
if server_name and #!cxtower.secret.FOLDER!# == "secretFolder":
    command = env["cx.tower.command"].create({{"name": "/opt/tower"}})
    COMMAND_RESULT = {{"exit_code": 0, "message": "New command was created"}}
else:
    COMMAND_RESULT = {{"exit_code": -1, "message": "error"}}
    """

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_pythonic,
            "Rendered code doesn't match",
        )

    def test_execute_python_command(self):
        """
        Execute command with python action.
        """
        command_result = self.server_test_1.with_context(no_log=True).execute_command(
            self.command_create_new_command
        )
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )
        self.assertEqual(
            command_result["response"],
            "New command was created",
            "The response must be text",
        )

        # Check error is raises
        self.secret_folder_key.secret_value = "not_a_secretFolder"
        command_result = self.server_test_1.with_context(no_log=True).execute_command(
            self.command_create_new_command
        )
        self.assertEqual(
            command_result["status"], -1, "The command result status must be -1"
        )
        self.assertEqual(
            command_result["error"],
            "error",
            "The error response must be contain text - error",
        )

    def test_execute_python_code(self):
        """
        Test python execution code
        """
        rendered_command = self.server_test_1._render_command(
            self.command_create_new_command
        )

        command_result = self.server_test_1._execute_python_code(
            rendered_command["rendered_code"]
        )
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )
        self.assertEqual(
            command_result["response"],
            "New command was created",
            "The response must be text",
        )
        self.assertIsNone(
            command_result["error"],
            "Error in command result must be set to None",
        )

    def test_execute_command_without_set_server_status(self):
        """
        Test command execution without setting server status
        """
        # Execute command
        server_status = self.server_test_1.status

        self.server_test_1.with_context(no_log=True).execute_command(
            self.command_create_new_command
        )

        # Check command result
        self.assertEqual(
            self.server_test_1.status, server_status, "Server status must be 'running'"
        )

    def test_execute_command_with_set_server_status(self):
        """
        Test command execution with setting server status
        """
        # Set server status to "down"
        self.command_create_new_command.write({"server_status": "stopping"})

        # Execute command
        self.server_test_1.with_context(no_log=True).execute_command(
            self.command_create_new_command
        )

        # Check command result
        self.assertEqual(
            self.server_test_1.status, "stopping", "Server status must be 'stopping'"
        )

    def test_execute_python_code_with_secret(self):
        """
        Test execution of Python code with a secret value.
        This test ensures that a command is rendered and executed correctly,
        and that the secret value is correctly handled and replaced in the output.
        """
        # Case 1
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_1
        )

        # Execute the rendered Python code
        command_result = self.server_test_1._execute_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            self.Key.SECRET_VALUE_SPOILER,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 2
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_2
        )

        # Execute the rendered Python code
        command_result = self.server_test_1._execute_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            f'We use "{self.Key.SECRET_VALUE_SPOILER}"',
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 3
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_3
        )

        # Execute the rendered Python code
        command_result = self.server_test_1._execute_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            self.Key.SECRET_VALUE_SPOILER,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 4
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_4
        )

        # Execute the rendered Python code
        command_result = self.server_test_1._execute_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            self.Key.SECRET_VALUE_SPOILER,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

    def test_command_with_secret(self):
        """
        Test case to verify that when a command includes a secret reference,
        the secret key is automatically linked with the command.
        """

        # Command with a secret reference
        code = "cd {{ test_path_ }} && mkdir #!cxtower.secret.FOLDER!#"

        secrets = self.Command._extract_secret_ids(code)
        secret_folder_key = self.secret_folder_key
        self.assertIn(
            secret_folder_key,
            secrets,
            msg=(
                f"The expected secret ID #{secret_folder_key.id} "
                "was not found in the provided code."
            ),
        )

        command_with_keys = self.Command.create(
            {"name": "Command with keys", "code": code}
        )

        # -- 1 --
        # Assert that the secret key is linked with the command
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )

        # -- 2 --
        #  Update the command's code to remove the secret reference
        updated_code = "cd {{ test_path_ }} && mkdir new_folder"
        command_with_keys.code = updated_code

        self.assertFalse(
            command_with_keys.secret_ids,
            msg=(
                "The secret_ids field should be empty after "
                "removing the secret reference from command."
            ),
        )

        # -- 3 --
        # Create a secret with the same reference but connected to another server
        another_server = self.server_test_1.copy({"name": "another server"})
        another_secret = self.Key.create(
            {
                "name": "another secret",
                "reference": secret_folder_key.reference,
                "server_id": another_server.id,
                "key_type": "k",
            }
        )
        # Set original code again
        command_with_keys.code = code
        self.assertEqual(
            len(command_with_keys.secret_ids),
            1,
            msg="Must be only one secret",
        )
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )
        self.assertNotIn(
            another_secret,
            command_with_keys.secret_ids,
            msg="The another secret is linked with the command.",
        )

        # -- 4 --
        # Connect command to server and secret to another server
        # and ensure it's unlinked from the command.
        yet_one_more_server = self.server_test_1.copy({"name": "yet one more server"})

        self.write_and_invalidate(
            secret_folder_key, **{"server_id": yet_one_more_server.id}
        )
        self.write_and_invalidate(
            command_with_keys, **{"server_ids": self.server_test_1}
        )
        self.assertEqual(
            len(command_with_keys.secret_ids),
            0,
            msg="Must be no secrets",
        )

        # -- 5 --
        # Add servers back to command and ensure secrets are linked
        self.write_and_invalidate(
            command_with_keys,
            **{"server_ids": another_server | self.server_test_1 | yet_one_more_server},
        )
        self.assertEqual(
            len(command_with_keys.secret_ids),
            2,
            msg="Must be two secrets",
        )
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )
        self.assertIn(
            another_secret,
            command_with_keys.secret_ids,
            msg="The another secret is not linked with the command.",
        )

        # -- 6 --
        # Link another secret to a new partner and ensure
        # it's not linked with the command
        another_partner = self.env["res.partner"].create({"name": "another partner"})
        self.write_and_invalidate(
            another_secret, **{"partner_id": another_partner.id, "server_id": False}
        )
        self.assertEqual(
            len(command_with_keys.secret_ids),
            1,
            msg="Must one secret",
        )
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )
        self.assertNotIn(
            another_secret,
            command_with_keys.secret_ids,
            msg="The another secret is linked with the command.",
        )

        # -- 7 --
        # Assign partner to a server and ensure secret is linked
        self.write_and_invalidate(
            self.server_test_1, **{"partner_id": another_partner.id}
        )
        self.assertEqual(
            len(command_with_keys.secret_ids),
            2,
            msg="Must be two secrets",
        )
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )
        self.assertIn(
            another_secret,
            command_with_keys.secret_ids,
            msg="The another secret is not linked with the command.",
        )
