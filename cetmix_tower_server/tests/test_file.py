from odoo import exceptions
from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerFile(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.file_template = self.FileTemplate.create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        self.file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.file_2 = self.File.create(
            {
                "name": "test.txt",
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
            }
        )

    def test_upload_file(self):
        """
        Upload file from tower to server
        """
        self.file.action_push_to_server()
        self.assertEqual(self.file.server_response, "ok")

    def test_delete_file(self):
        """
        Delete file remotely from server
        """
        result = self.file.action_delete_from_server()
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(result["params"]["message"], "File deleted!")

    def test_delete_file_access(self):
        """
        Test delete file access
        """
        with self.assertRaises(exceptions.AccessError):
            self.file.with_user(self.user_bob).delete(raise_error=True)

    def test_download_file(self):
        """
        Download file from server to tower
        """
        self.file_2.action_pull_from_server()
        self.assertEqual(self.file_2.code, "ok")

        self.file_2.name = "binary.zip"
        res = self.file_2.action_pull_from_server()
        self.assertTrue(
            isinstance(res, dict) and res["tag"] == "display_notification",
            msg=(
                "If file type is 'text', then the result must be a dict "
                "representing the display_notification action."
            ),
        )

    def test_get_current_server_code(self):
        """
        Download file from server to tower
        """
        self.file.action_push_to_server()
        self.assertEqual(self.file.server_response, "ok")

        self.file.action_get_current_server_code()
        self.assertEqual(self.file.code_on_server, "ok")

    def test_modify_template_code(self):
        """Test how template code modification affects related files"""
        code = "Pepe frog is happy as always"
        self.file_template.code = code

        # Check file code before modifications
        self.assertTrue(
            self.file.code == code,
            msg="File code must be the same "
            "as template code before any modifications",
        )
        # Check file rendered code before modifications
        self.assertTrue(
            self.file.rendered_code == code,
            msg="File rendered code must be the same"
            " as template code before any modifications",
        )

        # Make possible to modify file code
        self.file.action_modify_code()

        # Check if template was removed from file
        self.assertFalse(
            self.file.template_id,
            msg="File template should be removed after modifying code.",
        )

        # Check if file code remains the same
        self.assertTrue(
            self.file.code == code, msg="File code should be the same as template."
        )

    def test_modify_template_related_files(self):
        """
        Check that after change file template
        all related files will update
        """
        self.assertEqual(self.file_template.file_name, "test.txt")
        # related files
        self.assertTrue(
            all(file.name == "test.txt" for file in self.file_template.file_ids)
        )

        # update file template name
        self.file_template.file_name = "new_test.txt"
        # Related files must updated
        self.assertTrue(
            all(file.name == "new_test.txt" for file in self.file_template.file_ids)
        )

        self.assertEqual(self.file_template.code, "Hello, world!")
        # update file template code
        self.file_template.code = "New code"
        # Related files must updated
        self.assertTrue(
            all(file.code == "New code" for file in self.file_template.file_ids)
        )

    def test_create_file_with_template(self):
        """
        Test if file is created with template code
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )

        file = file_template.create_file(server=self.server_test_1)
        self.assertEqual(file.code, self.file_template.code)
        self.assertEqual(file.template_id, file_template)
        self.assertEqual(file.server_id, self.server_test_1)
        self.assertEqual(file.source, "tower")
        self.assertEqual(file.server_dir, self.file_template.server_dir)

        with self.assertRaises(exceptions.ValidationError):
            file_template.create_file(server=self.server_test_1, raise_if_exists=True)

        another_file = file_template.create_file(
            server=self.server_test_1, raise_if_exists=False
        )
        self.assertEqual(another_file, file)

    def test_create_file_with_template_custom_server_dir(self):
        """
        Test if file is created with template code and custom server dir
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )

        file = file_template.create_file(
            server=self.server_test_1, server_dir="/var/tmp/custom"
        )
        self.assertEqual(file.code, self.file_template.code)
        self.assertEqual(file.template_id, file_template)
        self.assertEqual(file.server_id, self.server_test_1)
        self.assertEqual(file.source, "tower")
        self.assertEqual(file.server_dir, "/var/tmp/custom")

        with self.assertRaises(exceptions.ValidationError):
            file_template.create_file(
                server=self.server_test_1,
                server_dir="/var/tmp/custom",
                raise_if_exists=True,
            )

        another_file = file_template.create_file(
            server=self.server_test_1,
            server_dir="/var/tmp/custom",
            raise_if_exists=False,
        )
        self.assertEqual(another_file, file)

    def test_files_access_rule(self):
        """
        Test access rules for files
        """
        # Remove user_bob from all cx_tower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Test that users can only read files where they are followers of the server
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        test_file_as_bob = self.file.with_user(self.user_bob)
        # Should not be able to read file where they are not follower
        with self.assertRaises(AccessError):
            file_read_result = test_file_as_bob.read([])
        # Should be able to read file where they are follower
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        file_read_result = test_file_as_bob.read([])
        self.assertEqual(
            file_read_result[0]["name"],
            self.file.name,
            msg="Users should have access to files assigned to servers to which "
            "they are subscribed",
        )
        # Test that users cannot write, create or delete files
        with self.assertRaises(AccessError):
            test_file_as_bob.write({"name": "new_name.txt"})
        with self.assertRaises(AccessError):
            self.File.with_user(self.user_bob).create(
                {
                    "name": "new_file.txt",
                    "source": "tower",
                    "server_id": self.server_test_1.id,
                    "server_dir": "/var/tmp",
                }
            )
        with self.assertRaises(AccessError):
            test_file_as_bob.unlink()
        # Test that managers can read, write and create files where they are followers
        # of the server
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Should be able to read file where they are follower
        file_read_result = test_file_as_bob.read([])
        self.assertEqual(
            file_read_result[0]["name"],
            self.file.name,
            msg="Managers should have access to files assigned to servers to which "
            "they are subscribed",
        )
        # Should be able to write to file where they are follower
        test_file_as_bob.write({"name": "updated_name.txt"})
        self.assertEqual(
            test_file_as_bob.name,
            "updated_name.txt",
            msg="Managers should have write access to files assigned to servers"
            " to which they are subscribed",
        )
        # Should be able to create file for server where they are follower
        new_file = self.File.with_user(self.user_bob).create(
            {
                "name": "new_file.txt",
                "source": "tower",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
            }
        )
        self.assertTrue(
            new_file.exists(),
            msg="Manager should be able to create a new file",
        )
        # Test that managers cannot delete files
        with self.assertRaises(AccessError):
            new_file.with_user(self.user_bob).unlink()
        # Should not be able to read file where they are not follower
        self.server_test_1.message_unsubscribe([self.user_bob.partner_id.id])
        with self.assertRaises(AccessError):
            file_read_result = new_file.with_user(self.user_bob).read([])
        # Should not be able to create file for server where they are not follower
        with self.assertRaises(AccessError):
            self.File.with_user(self.user_bob).create(
                {
                    "name": "new_file.txt",
                    "source": "tower",
                    "server_id": self.server_test_1.id,
                    "server_dir": "/var/tmp",
                }
            )

    def test_file_with_secret_key(self):
        """
        Test case to verify that when a file includes a secret reference,
        the secret key is automatically linked with the file.
        """

        # Create a secret key
        secret_python_key = self.Key.create(
            {
                "name": "python",
                "reference": "PYTHON",
                "secret_value": "secretPythonCode",
                "key_type": "s",
            }
        )

        # Create a file template with a reference to the secret key
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Please use this secret #!cxtower.secret.PYTHON!#",
            }
        )

        # Create a file from the file template
        file = file_template.create_file(
            server=self.server_test_1, server_dir="/var/tmp/custom"
        )

        # Assert that the file's code matches the file template's code
        self.assertEqual(
            file.code,
            file_template.code,
            msg="The file's code does not match the file template's code.",
        )

        # Assert that the secret key is associated with the file
        self.assertIn(
            secret_python_key,
            file.secret_ids,
            msg="The secret key is not associated with the file.",
        )

        # Update the file's code to remove the secret reference
        file.code = "Only text"

        self.assertFalse(
            file.secret_ids,
            msg=(
                "The secret_ids field should be empty after "
                "removing the secret reference from file."
            ),
        )

    def test_file_with_sensitive_variable(self):
        """
        Test case to verify that user has access to use file with sensitive variables.
        """
        # Create file with sensitive variable
        file = self.File.create(
            {
                "source": "tower",
                "name": "test.txt",
                "server_id": self.server_test_1.id,
                "code": "'IPv4 Address': {{ tower.server.ipv4 }}",
            }
        )
        # Remove user_bob from all cx_tower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Add bob to user group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Add bob as subscriber of the server to allow upload file
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        # Upload file to server
        self.assertTrue(file.server_response != "ok")
        file.with_user(self.user_bob).action_push_to_server()
        self.assertEqual(file.server_response, "ok")
