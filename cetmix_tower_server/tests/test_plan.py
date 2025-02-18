# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerPlan(TestTowerCommon):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # Command
        self.command_run_flight_plan_1 = self.Command.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": self.plan_1.id,
            }
        )

        # Flight plan
        self.plan_2 = self.Plan.create(
            {
                "name": "Test plan 2",
                "note": "Run another flight plan",
            }
        )
        self.plan_2_line_1 = self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )
        self.plan_2_line_2 = self.plan_line.create(
            {
                "sequence": 10,
                "command_id": self.command_create_dir.id,
            }
        )
        # Flight plan with access level 1 to test user access rights
        self.plan_3 = self.Plan.create(
            {
                "name": "Test plan 3",
                "note": "Test user access rights",
                "access_level": "1",
                "line_ids": [
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 1}),
                ],
            }
        )
        # Create line for plan 3
        self.plan_3_line_1 = self.plan_line.create(
            {
                "plan_id": self.plan_3.id,
                "command_id": self.command_create_dir.id,
                "sequence": 10,
            }
        )
        self.plan_3_line_1_action = self.env["cx.tower.plan.line.action"].create(
            {
                "line_id": self.plan_3_line_1.id,
                "condition": "==",
                "value_char": "test",
                "action": "e",
            }
        )
        self.variable_value = self.env["cx.tower.variable.value"].create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Windows 2k",
                "plan_line_action_id": self.plan_3_line_1_action.id,
            }
        )

    def test_plan_line_action_name(self):
        """Test plan line action naming"""

        # Add new line
        plan_line_1 = self.plan_line.create(
            {
                "plan_id": self.plan_1.id,
                "command_id": self.command_create_dir.id,
                "sequence": 10,
            }
        )

        # Add new action with custom
        action_1 = self.plan_line_action.create(
            {
                "line_id": plan_line_1.id,
                "condition": "==",
                "value_char": "35",
                "action": "e",
            }
        )

        # Check if action name is composed correctly
        expected_action_string = _(
            "If exit code == 35 then Exit with command exit code"
        )
        self.assertEqual(
            action_1.name,
            expected_action_string,
            msg="Action name doesn't match expected one",
        )

    def test_plan_get_next_action_values(self):
        """Test _get_next_action_values()

        NB: This test relies on demo data and might fail if it is modified
        """
        # Ensure demo date integrity just in case demo date is modified
        self.assertEqual(
            self.plan_1.line_ids[0].action_ids[1].custom_exit_code,
            255,
            "Plan 1 line #1 action #2 custom exit code must be equal to 255",
        )

        # Create a new plan log.
        plan_line_1 = self.plan_1.line_ids[0]  # Using command 1 from Plan 1
        plan_log = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_1.id,
                "is_running": True,
                "start_date": fields.Datetime.now(),
                "plan_line_executed_id": plan_line_1.id,
            }
        )

        # ************************
        # Test with exit code == 0
        # Must run the next command
        # ************************
        command_log = self.CommandLog.create(
            {
                "plan_log_id": plan_log.id,
                "server_id": self.server_test_1.id,
                "command_id": plan_line_1.command_id.id,
                "command_response": "Ok",
                "command_status": 0,  # Error code
            }
        )
        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Execute next action'")
        self.assertEqual(exit_code, 0, msg="Exit code must be equal to 0")
        self.assertEqual(
            next_line_id,
            self.plan_line_2,
            msg="Next line must be Line #2",
        )

        # ************************
        # Test with exit code == 8
        # Must exit with custom code
        # ************************
        command_log.command_status = 8

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "ec", msg="Action must be 'Exit with custom code'")
        self.assertEqual(exit_code, 255, msg="Exit code must be equal to 255")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Test with exit code == -12
        # Plan on error action must be triggered because no action condition is matched
        # ************************
        command_log.command_status = -12

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Change Plan 'On error action' of the plan to 'Run next command'
        # Next line must be Line #2
        # ************************

        command_log.command_status = -12
        self.plan_1.on_error_action = "n"

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Execute next action'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertEqual(
            next_line_id,
            self.plan_line_2,
            msg="Next line must be Line #2",
        )

        # ************************
        # Run Line 2 (the last one).
        # Action 2 will be triggered which is "Run next line".
        # However because this is the last line of the plan must exit with command code.
        # ************************

        plan_line_2 = self.plan_1.line_ids[1]
        plan_log.plan_line_executed_id = plan_line_2.id
        command_log.command_status = 3

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 3, msg="Exit code must be equal to 3")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Run Line 2 (the last one).
        # Fallback plan action must be triggered because no action condition is matched
        # However because this is the last line of the plan must exit with command code.
        # ************************

        command_log.command_status = 1

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 1, msg="Exit code must be equal to 1")
        self.assertIsNone(next_line_id, msg="Next line must be None")

    def test_plan_execute_single(self):
        """Test plan execution results"""
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)

        # Check plan log
        plan_log_rec = self.PlanLog.search([("server_id", "=", self.server_test_1.id)])

        # Must be a single record
        self.assertEqual(len(plan_log_rec), 1, msg="Must be a single plan record")

        # Ensure all commands were triggered
        expected_command_count = 2
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg=f"Must run {expected_command_count} commands",
        )

        # Check plan status
        expected_plan_status = 0
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg=f"Plan status must be equal to {expected_plan_status}",
        )

        # ************************
        # Change condition in line #1.
        # Action 1 will be triggered which is "Exit with custom code" 29.
        # ************************
        action_to_tweak = self.plan_line_1_action_1
        action_to_tweak.write({"custom_exit_code": 29, "action": "ec"})

        # Execute plan
        self.plan_1._execute_single(self.server_test_1)

        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        # Must be two plan log record
        self.assertEqual(len(plan_log_records), 2, msg="Must be 2 plan log records")
        plan_log_rec = plan_log_records[0]

        # Ensure all commands were triggered
        expected_command_count = 1
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg=f"Must run {expected_command_count} commands",
        )

        # Check plan status
        expected_plan_status = 29
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg=f"Plan status must be equal to {expected_plan_status}",
        )

        # Ensure 'path' was substituted with the plan line custom 'path'
        self.assertEqual(
            self.plan_line_1.path,
            plan_log_rec.command_log_ids.path,
            "Path in command log must be the same as in the flight plan line",
        )

    def test_plan_user_access_rule(self):
        """Test plan user access rule"""
        # Create the test plan without assigned plan.lines
        self.plan_2 = self.Plan.create(
            {
                "name": "Test plan 2",
                "note": "Create directory and list its content",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            }
        )
        # Ensure that defaulf command access_level is equal to 2

        self.assertEqual(self.plan_2.access_level, "2")
        self.plan_2.write({"access_level": "1"})

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot access the plan

        test_plan_2_as_bob = self.plan_2.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            plan_name = test_plan_2_as_bob.name

        # Add user to group_user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Ensure that user can access the plan with access_level 1
        plan_name = test_plan_2_as_bob.name
        self.assertEqual(plan_name, test_plan_2_as_bob.name, msg="Name must be equal")
        # Add user to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Check if manager can modify exisiting  plan
        test_plan_2_as_bob.write({"access_level": "2"})
        self.assertEqual(test_plan_2_as_bob.access_level, "2")

        # Check if manager can create a new  plan
        self.plan_3 = self.Plan.with_user(self.user_bob).create(
            {
                "name": "Test plan 3",
                "note": "Create directory and list its content",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            }
        )
        self.assertTrue(
            self.plan_3.exists(),
            msg="Manager should be able to create a new plan",
        )

        # Check what manager can't unlink existing plan
        with self.assertRaises(AccessError):
            self.plan_3.with_user(self.user_bob).unlink()

        # Add user_bob to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Check what root can unlink existing plan
        self.plan_3.with_user(self.user_bob).unlink()
        self.assertFalse(self.plan_3.exists(), "Plan should be unlinked and not exist")
        # Remove user_bob from root group to test access to flight plans related
        # to servers user isn't subscribed
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_root",
            ],
        )
        # Assign plan_1 to self.server_test_1
        self.write_and_invalidate(
            self.plan_2, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )

        # Ensure Bob can't access plan as manager if he is not a follower
        #  of self.server_test_1
        with self.assertRaises(AccessError):
            self.plan_2.with_user(self.user_bob).read([])
        # Subscribe Bob to self.server_test_1
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        # Ensure Bob can now access plan as a follower of self.server_test_1
        plan_2_read_result = self.plan_2.with_user(self.user_bob).read([])
        self.assertEqual(
            plan_2_read_result[0]["name"],
            self.plan_2.name,
            msg="Plan name should be same",
        )
        # Remove Bob from manager group
        self.remove_from_group(self.user_bob, ["cetmix_tower_server.group_manager"])
        # Change plan access level
        self.write_and_invalidate(self.plan_2, **{"access_level": "1"})

        # Ensure Bob retains access to plan_2 as user because he is a follower
        plan_2_read_result = self.plan_2.with_user(self.user_bob).read([])
        self.assertEqual(
            plan_2_read_result[0]["name"],
            self.plan_2.name,
            msg="Plan name should be same",
        )

    def test_plan_and_command_access_level(self):
        # Remove userbob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Add user_bob to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # check if plan and commands included has same access level
        self.assertEqual(self.plan_1.access_level, "2")
        self.assertEqual(self.command_create_dir.access_level, "2")
        self.assertEqual(self.command_list_dir.access_level, "2")
        # check that if we modify plan access level to make it lower than the
        # access_level of the commands related with it access level,
        # access_level_warn_msg will be created
        self.plan_1.with_user(self.user_bob).write({"access_level": "1"})
        self.assertTrue(self.plan_1.access_level_warn_msg)

        # Add user_bob to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        # check if user_bob can make plan access leve higher than commands access level
        self.plan_1.with_user(self.user_bob).write({"access_level": "3"})
        self.assertEqual(self.plan_1.access_level, "3")
        # check that if we create a new plan with an access_level lower than
        # the access_level of the command related with access_level_warn_msg
        #  will be created
        command_1 = self.Command.create(
            {"name": "New Test Command", "access_level": "3"}
        )

        self.plan_2 = self.Plan.create(
            {
                "name": "Test plan 2",
                "note": "Create directory and list its content",
            }
        )
        self.plan_line_2_1 = self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.plan_2.id,
                "command_id": command_1.id,
            }
        )
        self.assertTrue(self.plan_2.access_level_warn_msg)

    def test_multiple_plan_create_write(self):
        """Test multiple plan create/write cases"""
        # Create multiple plans at once
        plans_data = [
            {
                "name": "Test Plan 1",
                "note": "Plan 1 Note",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            },
            {
                "name": "Test Plan 2",
                "note": "Plan 2 Note",
                "tag_ids": [(6, 0, [self.tag_test_production.id])],
            },
            {
                "name": "Test Plan 3",
                "note": "Plan 3 Note",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            },
        ]
        created_plans = self.Plan.create(plans_data)
        # Check that all plans are created successfully
        self.assertTrue(all(created_plans))
        # Update the access level of the created plans
        created_plans.write({"access_level": "3"})
        # Check that all plans are updated successfully
        self.assertTrue(all(plan.access_level == "3" for plan in created_plans))

    def test_plan_with_first_not_executable_condition(self):
        """
        Test plan with not executable condition for first plan line
        """
        # Add condition for the first plan line
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            plan_log_records.command_log_ids[0].is_skipped,
            msg="First command must be skipped",
        )
        self.assertFalse(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command not must be skipped",
        )

    def test_plan_with_second_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for second plan line
        self.plan_line_2.condition = "{{ odoo_version }} == '14.0'"
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command must be skipped",
        )
        self.assertFalse(
            plan_log_records.command_log_ids[0].is_skipped,
            msg="First command not must be skipped",
        )

    def test_plan_with_executable_condition(self):
        """
        Test plan with executable condition for plan line
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "1 == 1"
        # Create a global value for the 'Version' variable
        self.VariableValue.create(
            {"variable_id": self.variable_version.id, "value_char": "14.0"}
        )
        # Add condition with variable
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '14.0'"
        )
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check commands
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            all(not command.is_skipped for command in plan_log_records.command_log_ids),
            msg="All command should be executed",
        )

    def test_plan_with_update_variables(self):
        """
        Test plan with update server variables
        """
        # Add new variable to server
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "14.0",
                "server_id": self.server_test_1.id,
            }
        )
        # Create new variable value to action to update existing server variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "16.0",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Check that server contains server variable with value
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_version
        )
        self.assertEqual(
            len(exist_server_values),
            1,
            "The server should have only one value for the variable",
        )
        self.assertEqual(
            exist_server_values.value_char,
            "14.0",
            "The server variable value should be '14.0'",
        )

        # Add a new variable value to an action that does not exist on the server
        self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Check that this field is not exist on server
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_os
        )
        self.assertFalse(
            exist_server_values, "The server should not have this variable"
        )
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check that exists server values was updated
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_version
        )
        self.assertEqual(
            len(exist_server_values),
            1,
            "The server should have only one value for the variable",
        )
        self.assertEqual(
            exist_server_values.value_char,
            "16.0",
            "The server variable value should be updated value '16.0'",
        )
        # Check that new server value was added to server
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_os
        )
        self.assertEqual(
            len(exist_server_values),
            1,
            "The server should have new value for the variable",
        )
        self.assertEqual(
            exist_server_values.value_char,
            "Ubuntu",
            "The server variable value should be updated value 'Ubuntu'",
        )

    def test_plan_with_action_variables_for_condition(self):
        """
        Test plan with update server variables and use new
        value as condition for next plan line
        """
        # Add new variable to server
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "14.0",
                "server_id": self.server_test_1.id,
            }
        )
        # Create new variable value to action to update existing server variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "16.0",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Add condition with variable
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '14.0'"
        )
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check commands
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # The second line of the plan should be skipped because the
        # first line of the plan updated the value of the variable
        self.assertTrue(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command must be skipped",
        )

        # Change condition for plan line
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '16.0'"
        )
        # Execute plan
        self.plan_1._execute_single(self.server_test_1)
        # Check commands
        new_plan_log_records = (
            self.PlanLog.search([("server_id", "=", self.server_test_1.id)])
            - plan_log_records
        )
        # The second line of the plan should be skipped because the
        # first line of the plan updated the value of the variable
        self.assertFalse(
            new_plan_log_records.command_log_ids[1].is_skipped,
            msg="The second plan line should not be skipped",
        )

    def test_flight_plan_copy(self):
        """Test duplicating a Flight Plan with lines, actions, and variable values"""

        # Create a Flight Plan
        plan = self.Plan.create(
            {
                "name": "Test Flight Plan",
                "note": "Test Note",
            }
        )

        # Create a command for the plan line
        command = self.Command.create(
            {
                "name": "Test Command",
                # Command to get Linux kernel version
                "code": "uname -r",
            }
        )

        # Create a Flight Plan Line
        plan_line = self.plan_line.create(
            {
                "plan_id": plan.id,
                "command_id": command.id,
                "path": "/test/path",
                # Condition based on Linux version
                "condition": '{{ test_linux_version }} >= "5.0"',
            }
        )

        # Create a variable for the action
        variable = self.Variable.create({"name": "test_linux_version"})

        # Create an Action for the Plan Line
        action = self.plan_line_action.create(
            {
                "line_id": plan_line.id,
                "action": "n",  # next action
                "condition": "==",
                "value_char": "0",  # condition for success
            }
        )

        # Create a Variable Value for the Action
        self.env["cx.tower.variable.value"].create(
            {
                "variable_id": variable.id,
                "value_char": "5.0",
                "plan_line_action_id": action.id,
            }
        )

        # Duplicate the Flight Plan
        copied_plan = plan.copy()

        # Ensure the new Flight Plan was created with a new ID
        self.assertNotEqual(
            copied_plan.id,
            plan.id,
            "Copied plan should have a different ID from the original",
        )

        # Check that the copied plan has the same number of lines
        self.assertEqual(
            len(copied_plan.line_ids),
            len(plan.line_ids),
            "Copied plan should have the same number of lines as the original",
        )

        # Check that the copied plan's lines have the same actions as the original
        original_line = plan.line_ids
        copied_line = copied_plan.line_ids

        # Ensure the command, condition, and custom path are copied correctly
        self.assertEqual(
            copied_line.command_id.id,
            original_line.command_id.id,
            "Command should be the same in copied line",
        )
        self.assertEqual(
            copied_line.path,
            original_line.path,
            "Custom path should be the same in copied line",
        )
        self.assertEqual(
            copied_line.condition,
            original_line.condition,
            "Condition should be the same in copied line",
        )

        # Ensure actions were copied correctly
        self.assertEqual(
            len(copied_line.action_ids),
            len(original_line.action_ids),
            "Number of actions should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.action,
            original_line.action_ids.action,
            "Action should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.condition,
            original_line.action_ids.condition,
            "Action condition should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.value_char,
            original_line.action_ids.value_char,
            "Action value should be the same in the copied line",
        )

        # Check that variable values were copied correctly
        original_action = original_line.action_ids
        copied_action = copied_line.action_ids

        self.assertEqual(
            len(copied_action.variable_value_ids),
            len(original_action.variable_value_ids),
            "Number of variable values should be the same in the copied action",
        )

        self.assertEqual(
            copied_action.variable_value_ids.variable_id.id,
            original_action.variable_value_ids.variable_id.id,
            "Variable should be the same in the copied action",
        )
        self.assertEqual(
            copied_action.variable_value_ids.value_char,
            original_action.variable_value_ids.value_char,
            "Variable value should be the same in the copied action",
        )

    def test_plan_with_another_plan(self):
        """
        Test to check running another plan from current plan
        """
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, 0, "Plan log should success status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )
        self.assertEqual(
            parent_plan_log.command_log_ids.triggered_plan_log_id,
            child_plan_log,
            "The command triggered plan line should be equal to child plan",
        )

        # Check that we cannot add recursive plan
        with self.assertRaisesRegex(
            ValidationError, "Recursive plan call detected in plan.*"
        ):
            self.plan_line.create(
                {
                    "sequence": 20,
                    "plan_id": self.plan_1.id,
                    "command_id": self.command_run_flight_plan_1.id,
                }
            )

        # Delete plan lines from first plan
        self.plan_1.line_ids = False
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)
        plan_log_records = (
            self.PlanLog.search([("server_id", "=", self.server_test_1.id)])
            - plan_log_records
        )

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, -1, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of parent plan should be equal "
            "of status second flight plan",
        )

    def test_plan_with_two_plans(self):
        """
        Test to check two plans from plan
        """
        self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

    def test_plan_with_nested_plans(self):
        """
        Test to check two plans from plan
        """
        command_run_flight_plan_2 = self.Command.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": self.plan_2.id,
            }
        )
        plan_3 = self.Plan.create(
            {
                "name": "Test plan 3",
                "note": "Run flight plan 2",
            }
        )
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": plan_3.id,
                "command_id": command_run_flight_plan_2.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        plan_3._execute_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

        last_child_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_1
        )
        self.assertTrue(last_child_plan_log, "The log for Plan 1 must exist!")
        self.assertEqual(
            last_child_plan_log.plan_status, 0, "Plan log should success status"
        )

        self.assertIn(
            last_child_plan_log.parent_flight_plan_log_id,
            plan_log_records,
            "Parent plan logs should exist",
        )
        self.assertEqual(
            last_child_plan_log.parent_flight_plan_log_id.plan_id,
            self.plan_2,
            "Parent plan should be equal to plan 2",
        )

        child_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertIn(
            child_plan_log.parent_flight_plan_log_id,
            plan_log_records,
            "Parent plan logs should exist",
        )
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id.plan_id,
            plan_3,
            "Parent plan should be equal to plan 3",
        )
        self.assertEqual(
            child_plan_log.command_log_ids.triggered_plan_log_id,
            last_child_plan_log,
            "The command triggered plan line should be equal to last child plan",
        )
        self.assertEqual(
            child_plan_log.command_log_ids.triggered_plan_log_id,
            last_child_plan_log,
            "The command triggered plan line should be equal to last child plan",
        )
        parent_plan_log = plan_log_records - child_plan_log - last_child_plan_log
        self.assertEqual(
            parent_plan_log.command_log_ids.triggered_plan_log_id,
            child_plan_log,
            "The command triggered plan line from parent plan "
            "should be equal to child plan",
        )

        # Check that we cannot change command with existing plan,
        # because it's recursive plan
        with self.assertRaisesRegex(
            ValidationError, "Recursive plan call detected in plan.*"
        ):
            self.plan_line_1.write(
                {
                    "command_id": command_run_flight_plan_2.id,
                }
            )

    def test_failed_first_child_plan_with_another_plan(self):
        """
        Check that child plan was failed then parent plan is failed too
        """
        # Add new plan line
        self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")

        # Simulate a failed Plan 1. To achieve this, we need to update the command
        # associated with Plan 1 to apply the desired side effect.
        self.plan_1.line_ids.command_id[0].code = "fail"

        # Execute plan
        self.plan_2._execute_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # 2 logs only because plan should exist with error after first failed command
        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, -1, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )

    def test_failed_second_child_plan_with_another_plan(self):
        """
        Check that child plan was failed then parent plan is failed too
        """
        # Add new plan line
        line = self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )

        cx_tower_plan_obj = self.registry["cx.tower.plan"]
        _execute_single_super = cx_tower_plan_obj._execute_single

        def _execute_single(this, *args, **kwargs):
            if (
                this == self.plan_1
                and this.env["cx.tower.plan.log"]
                .browse(kwargs["log"]["plan_log_id"])
                .plan_line_executed_id
                == line
            ):
                # Simulate a failed Plan 1. To achieve this, we need to update
                # the command associated with Plan 1 to apply the desired side effect.
                self.plan_1.line_ids.command_id[0].code = "fail"
            return _execute_single_super(this, *args, **kwargs)

        with patch.object(cx_tower_plan_obj, "_execute_single", _execute_single):
            # Execute plan
            self.plan_2._execute_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # 3 logs because plan should exist with error after second failed command
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, -1, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            len(child_plan_log),
            2,
            "Must be 2 child plan logs",
        )
        self.assertIn(
            -1,
            child_plan_log.mapped("plan_status"),
            "One of plan status of child plan must be -1",
        )
        self.assertIn(
            0,
            child_plan_log.mapped("plan_status"),
            "One of plan status of child plan must be -1",
        )

    def test_plan_with_another_plan_with_condition(self):
        """
        Test that parent plan will success finished
        if child plan executable by condition
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "1 == 1"
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, 0, "Plan log should success status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )

    def test_plan_with_another_plan_with_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        self.assertIn(
            -20,
            plan_log_records.command_log_ids.mapped("command_status"),
            "One of commands should be skipped",
        )

    def test_plan_with_another_plan_with_all_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for all plan lines
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        self.plan_line_2.condition = "{{ odoo_version }} == '14.0'"

        self.plan_2_line_1.condition = "{{ odoo_version }} == '14.0'"
        self.plan_2_line_2.condition = "{{ odoo_version }} == '14.0'"

        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Execute plan
        self.plan_2._execute_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 1, msg="Should be 1 plan logs")
        self.assertEqual(
            -20,
            plan_log_records.command_log_ids.command_status,
            "Command status should be skipped",
        )

    def test_plan_unlink(self):
        plan = self.plan_1.copy()
        plan_id = plan.id
        plan_line_ids = plan.line_ids
        plan_line_action_ids = plan.mapped("line_ids.action_ids")

        plan.unlink()

        self.assertFalse(
            self.Plan.search([("id", "=", plan_id)]), msg="Plan should be deleted"
        )
        self.assertFalse(
            self.plan_line.search([("id", "in", plan_line_ids.ids)]),
            msg="Plan line should be deleted when Plan is deleted",
        )
        self.assertFalse(
            self.plan_line_action.search([("id", "in", plan_line_action_ids.ids)]),
            msg="Plan line action should be deleted when Plan line is deleted",
        )

    def test_plan_lines_user_access_rights(self):
        """
        Test user access rights for plan lines
        """
        # Ensure that user without any group cannot access plan lines
        test_plan_3_as_bob = self.plan_3.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        # Add user_bob to `group_user` and test plan.line access
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        self.assertEqual(
            plan_line_read_result[0]["name"],
            "Test create directory",
            msg="User should access plan lines with access_level 1",
        )
        # Test that user cannot write to plan lines
        with self.assertRaises(AccessError):
            test_plan_3_as_bob.line_ids[0].write({"sequence": 10})

        # Test that user cannot unlink plan lines
        with self.assertRaises(AccessError):
            test_plan_3_as_bob.line_ids[0].unlink()

    def test_plan_lines_subscribed_user_access_rights(self):
        """
        Test user access to the plan lines assigned to the server they are subscribed to
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Assign Plan_3 to the server_test_1
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )
        # Ensure that user not subscribed to the server cannot access plan lines
        test_plan_3_as_bob = self.plan_3.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        # Subscribe user to the server
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        # Check that user can access plan lines
        plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        self.assertEqual(
            plan_line_read_result[0]["name"],
            "Test create directory",
            msg="User should access plan lines assigned to the server "
            "they are subscribed to",
        )

    def test_plan_lines_manager_access_rights(self):
        """
        Test manager access rights for plan lines
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_plan_3_as_bob = self.plan_3.with_user(self.user_bob)
        # Test that manager can write to plan lines
        test_plan_3_as_bob.line_ids[0].write({"sequence": 10})
        self.assertEqual(
            test_plan_3_as_bob.line_ids[0].sequence,
            10,
            msg="Manager should be able to update sequence",
        )
        # Test that manager can not unlink plan lines they did not create
        with self.assertRaises(AccessError):
            test_plan_3_as_bob.line_ids[0].unlink()
        # Test that manager can create plan lines
        plan_line_as_bob = self.plan_line.with_user(self.user_bob).create(
            {
                "plan_id": test_plan_3_as_bob.id,
                "command_id": self.command_create_dir.id,
                "sequence": 11,
            }
        )
        self.assertTrue(
            plan_line_as_bob.exists(),
            msg="Manager should be able to create plan lines",
        )
        # Test that manager can delete plan lines they created
        plan_line_as_bob.unlink()
        self.assertFalse(
            plan_line_as_bob.exists(),
            msg="Manager should be able to delete own plan lines",
        )

    def test_plan_lines_subscribed_manager_access_rights(self):
        """
        Test manager access rights for plan lines assigned to the server they are
        subscribed to
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Assign Plan_3 to the server_test_1
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )
        # Ensure that manager without subscribing to the server cannot access plan lines
        test_plan_3_as_bob = self.plan_3.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        # Subscribe manager to the server
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        # Check that manager can access plan lines
        plan_line_read_result = test_plan_3_as_bob.line_ids[0].read([])
        self.assertEqual(
            plan_line_read_result[0]["name"],
            "Test create directory",
            msg="Manager should access plan lines assigned to the server "
            "they are subscribed to",
        )
        # Test that manager can create lines assigned to the server they are
        #  subscribed to
        plan_line_as_bob = self.plan_line.with_user(self.user_bob).create(
            {
                "plan_id": test_plan_3_as_bob.id,
                "command_id": self.command_create_dir.id,
                "sequence": 12,
            }
        )
        self.assertTrue(
            plan_line_as_bob.exists(),
            msg="Manager should be able to create plan lines assigned to the server "
            "they are subscribed to",
        )
        # Test that manager has no access to lines assigned to the server they
        # are not subscribed to
        self.server_test_1.message_unsubscribe([self.user_bob.partner_id.id])
        with self.assertRaises(AccessError):
            plan_line_read_result = test_plan_3_as_bob.read([])

    def test_plan_line_action_user_access_rights(self):
        """
        Test user access rights for plan line actions
        """
        # Ensure user without any group cannot access plan line actions
        test_action_as_bob = self.plan_3_line_1_action.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            test_action_as_bob.read([])

        # Add user to group_user and test access
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # User should be able to read plan line actions
        action_read_result = test_action_as_bob.read([])
        self.assertEqual(
            action_read_result[0]["condition"],
            "==",
            msg="User should be able to read plan line actions",
        )

        # User should not be able to create/write/unlink
        with self.assertRaises(AccessError):
            self.env["cx.tower.plan.line.action"].with_user(self.user_bob).create(
                {
                    "line_id": self.plan_3_line_1.id,
                    "condition": "==",
                    "value_char": "test2",
                    "action": "e",
                }
            )

        with self.assertRaises(AccessError):
            test_action_as_bob.write({"value_char": "modified"})

        with self.assertRaises(AccessError):
            test_action_as_bob.unlink()

    def test_plan_line_action_subscribed_user_access_rights(self):
        """
        Test user access rights for plan line actions assigned to servers
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Assign plan to server
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )

        # User not subscribed - should not have access
        test_action_as_bob = self.plan_3_line_1_action.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            test_action_as_bob.read([])

        # Subscribe user to server
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])

        # User should now have read access
        action_read_result = test_action_as_bob.read([])
        self.assertEqual(
            action_read_result[0]["condition"],
            "==",
            msg="Subscribed user should be able to read plan line actions",
        )

    def test_plan_line_action_manager_access_rights(self):
        """
        Test manager access rights for plan line actions
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_action_as_bob = self.plan_3_line_1_action.with_user(self.user_bob)

        # Manager should be able to read and write
        action_read_result = test_action_as_bob.read([])
        self.assertEqual(
            action_read_result[0]["condition"],
            "==",
            msg="Manager should be able to read plan line actions",
        )

        test_action_as_bob.write({"value_char": "modified"})
        self.assertEqual(
            test_action_as_bob.value_char,
            "modified",
            msg="Manager should be able to modify plan line actions",
        )

        # Manager should be able to create own actions
        new_action_as_bob = (
            self.env["cx.tower.plan.line.action"]
            .with_user(self.user_bob)
            .create(
                {
                    "line_id": self.plan_3_line_1.id,
                    "condition": "==",
                    "value_char": "test2",
                    "action": "e",
                }
            )
        )

        self.assertTrue(
            new_action_as_bob.exists(),
            msg="Manager should be able to create plan line actions",
        )

        # Manager should be able to delete own actions but not others
        with self.assertRaises(AccessError):
            test_action_as_bob.unlink()

        new_action_as_bob.unlink()
        self.assertFalse(
            new_action_as_bob.exists(),
            msg="Manager should be able to delete own plan line actions",
        )

    def test_plan_line_action_subscribed_manager_access_rights(self):
        """
        Test manager access rights for plan line actions assigned to servers
        """
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Assign plan to server
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )
        test_action_as_bob = self.plan_3_line_1_action.with_user(self.user_bob)

        # Manager not subscribed - should not have access
        with self.assertRaises(AccessError):
            test_action_as_bob.read([])

        # Subscribe manager to server
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])

        # Manager should now have full access
        action_read_result = test_action_as_bob.read([])
        self.assertEqual(
            action_read_result[0]["condition"],
            "==",
            msg="Subscribed manager should be able to read plan line actions",
        )

        # Create own action as subscribed manager
        new_action_as_bob = (
            self.env["cx.tower.plan.line.action"]
            .with_user(self.user_bob)
            .create(
                {
                    "line_id": self.plan_3_line_1.id,
                    "condition": "==",
                    "value_char": "test2",
                    "action": "e",
                }
            )
        )
        self.assertTrue(
            new_action_as_bob.exists(),
            msg="Subscribed manager should be able to create plan line actions",
        )
        # Test that manager has no access to lines assigned to the server they
        # are not subscribed to
        self.server_test_1.message_unsubscribe([self.user_bob.partner_id.id])
        with self.assertRaises(AccessError):
            new_action_as_bob.read([])

    def test_plan_line_action_variable_values_user_access_rights(self):
        """
        Test user access rights for variable values associated with plan line actions
        """
        # group_user: Plan not assigned to server, ensure access to variable value in
        #  plan line action
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        test_plan_line_action_as_bob = self.plan_3_line_1_action.with_user(
            self.user_bob
        )
        plan_line_action_vv_read_result = (
            test_plan_line_action_as_bob.variable_value_ids.read([])
        )
        self.assertEqual(
            plan_line_action_vv_read_result[0]["value_char"],
            self.variable_value.value_char,
            msg="Value should be the same",
        )
        # User not subscribed to the server: ensure no access to variable value in
        # plan line action
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )
        with self.assertRaises(AccessError):
            plan_line_action_vv_read_result = (
                test_plan_line_action_as_bob.variable_value_ids.read([])
            )
        # User subscribed to the server: ensure access to variable value in
        # plan line action
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        plan_line_action_vv_read_result = (
            test_plan_line_action_as_bob.variable_value_ids.read([])
        )
        self.assertEqual(
            plan_line_action_vv_read_result[0]["value_char"],
            self.variable_value.value_char,
            msg="Value should be the same",
        )

    def test_plan_line_action_variable_values_manager_access_rights(self):
        """
        Test manager access rights for variable values associated with plan line actions
        """
        # add user_bob to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        self.write_and_invalidate(
            self.plan_3, **{"server_ids": [(6, 0, [self.server_test_1.id])]}
        )

        # Manager subscribed to the server: ensure user_bob cannot remove variable value
        # from action line if he is not creator of variable
        with self.assertRaises(AccessError):
            self.variable_value.with_user(self.user_bob).unlink()
        # User subscribed to the server: ensure user_bob can create variable value in
        # plan line action
        variable_value_as_bob = (
            self.env["cx.tower.variable.value"]
            .with_user(self.user_bob)
            .create(
                {
                    "variable_id": self.variable_os.id,
                    "value_char": "OS/2",
                }
            )
        )

        plan_line_action_as_bob = (
            self.env["cx.tower.plan.line.action"]
            .with_user(self.user_bob)
            .create(
                {
                    "line_id": self.plan_3_line_1.id,
                    "condition": ">",
                    "value_char": "100",
                    "action": "e",
                    "variable_value_ids": [(4, variable_value_as_bob.id)],
                }
            )
        )

        # Ensure that variable value has assigned properly
        self.assertIn(
            variable_value_as_bob.id,
            plan_line_action_as_bob.variable_value_ids.ids,
            msg="variable_value_ids should contain variable_value.id",
        )
        # User subscribed to the server: ensure user_bob can delete their own variable
        # value from  plan line action he created
        variable_value_as_bob.unlink()
        # Ensure the variable value has been deleted
        self.assertFalse(
            variable_value_as_bob.exists(),
            msg="Manager should be able to delete own plan line action variable value",
        )
