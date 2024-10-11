import yaml

from odoo.tests import TransactionCase


class TestTowerCommand(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        self.Command = self.env["cx.tower.command"]

        # Expected YAML content of the test command
        self.command_test_yaml = """access_level: manager
action: ssh_command
allow_parallel_run: false
cetmix_tower_model: command
cetmix_tower_yaml_version: 1
code: |-
  cd /home/{{ tower.server.ssh_username }} \\
  && ls -lha
name: Test YAML
note: |-
  Test YAML command conversion.
  Ensure all fields are rendered properly.
path: false
reference: test_yaml_in_tests
"""

        # YAML content translated into Python dict
        self.command_test_yaml_dict = yaml.safe_load(self.command_test_yaml)

    def test_yaml_from_command(self):
        """Test if YAML is generated properly from a command"""

        # -- 0 --
        # Create test command
        # Test command
        command_test = self.Command.create(
            {
                "name": "Test YAML",
                "reference": "test_yaml_in_tests",
                "action": "ssh_command",
                "code": """cd /home/{{ tower.server.ssh_username }} \\
&& ls -lha""",
                "note": """Test YAML command conversion.
Ensure all fields are rendered properly.""",
            }
        )

        # -- 1 --
        # Check it YAML generated by the command matches
        # YAML from the template file

        self.assertEqual(
            command_test.yaml_code,
            self.command_test_yaml,
            "YAML generated from command doesn't match template file one",
        )

        # -- 2 --
        # Check if YAML key values match Cetmix Tower ones

        self.assertEqual(
            command_test.access_level,
            self.Command.TO_TOWER_ACCESS_LEVEL[
                self.command_test_yaml_dict["access_level"]
            ],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.action,
            self.command_test_yaml_dict["action"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.allow_parallel_run,
            self.command_test_yaml_dict["allow_parallel_run"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            self.Command.CETMIX_TOWER_YAML_VERSION,
            self.command_test_yaml_dict["cetmix_tower_yaml_version"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.code,
            self.command_test_yaml_dict["code"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.name,
            self.command_test_yaml_dict["name"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.note,
            self.command_test_yaml_dict["note"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.path,
            self.command_test_yaml_dict["path"],
            "YAML value doesn't match Cetmix Tower one",
        )
        self.assertEqual(
            command_test.reference,
            self.command_test_yaml_dict["reference"],
            "YAML value doesn't match Cetmix Tower one",
        )

    # TODO: need to fix reference creation for this test to run
    # https://github.com/cetmix/cetmix-tower/pull/102
    def no_test_command_from_yaml(self):
        """Test if YAML is generated properly from a command"""

        def test_yaml(command):
            """Checks if yaml values are inserted correctly

            Args:
                command(cx.tower.command): _description_
            """
            self.assertEqual(
                command.access_level,
                self.Command.TO_TOWER_ACCESS_LEVEL[
                    self.command_test_yaml_dict["access_level"]
                ],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.action,
                self.command_test_yaml_dict["action"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.allow_parallel_run,
                self.command_test_yaml_dict["allow_parallel_run"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                self.Command.CETMIX_TOWER_YAML_VERSION,
                self.command_test_yaml_dict["cetmix_tower_yaml_version"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.code,
                self.command_test_yaml_dict["code"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.name,
                self.command_test_yaml_dict["name"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.note,
                self.command_test_yaml_dict["note"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.path,
                self.command_test_yaml_dict["path"],
                "YAML value doesn't match Cetmix Tower one",
            )
            self.assertEqual(
                command.reference,
                self.command_test_yaml_dict["reference"],
                "YAML value doesn't match Cetmix Tower one",
            )

        # Create test command
        command_test = self.Command.create(
            {"name": "New Command", "action": "python_code"}
        )

        # -- 1 --
        # Insert YAML into the command and
        #   check if YAML key values match Cetmix Tower ones
        command_test.yaml_code = self.command_test_yaml
        test_yaml(command_test)

        # -- 2 --
        #  Insert some non supported keys and ensure nothing bad happens
        yaml_with_non_supported_keys = """access_level: manager
action: ssh_command
doge: wow
memes: much nice!
allow_parallel_run: false
cetmix_tower_model: command
cetmix_tower_yaml_version: 1
code: |-
  cd /home/{{ tower.server.ssh_username }} \\
  && ls -lha
name: Test YAML
note: |-
  Test YAML command conversion.
  Ensure all fields are rendered properly.
path: false
reference: test_yaml_in_tests
"""
        command_test.yaml_code = yaml_with_non_supported_keys
        test_yaml(command_test)
