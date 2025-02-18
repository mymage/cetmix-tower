# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv.expression import OR


class TowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _description = "Cetmix Tower Variable Values"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _rec_name = "variable_reference"
    _order = "variable_reference"

    variable_id = fields.Many2one(
        string="Variable",
        comodel_name="cx.tower.variable",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(related="variable_id.name", readonly=True)
    variable_reference = fields.Char(
        string="Variable Reference",
        related="variable_id.reference",
        store=True,
        index=True,
    )
    is_global = fields.Boolean(
        string="Global",
        compute="_compute_is_global",
        inverse="_inverse_is_global",
        store=True,
    )
    note = fields.Text(related="variable_id.note", readonly=True)
    active = fields.Boolean(default=True)
    variable_type = fields.Selection(
        related="variable_id.variable_type",
        readonly=True,
    )
    option_id = fields.Many2one(
        comodel_name="cx.tower.variable.option",
        ondelete="restrict",
        domain="[('variable_id', '=', variable_id)]",
    )
    value_char = fields.Char(
        string="Value",
        compute="_compute_value_char",
        inverse="_inverse_value_char",
        store=True,
        readonly=False,
    )

    # Direct model relations.
    # Following functions should be updated when a new m2o field is added:
    #   -  `_used_in_models()`
    #   -  `_compute_is_global()`: add you field to 'depends'
    # Define a `unique` constraint for new model too.
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", index=True, ondelete="cascade"
    )
    plan_line_action_id = fields.Many2one(
        comodel_name="cx.tower.plan.line.action", index=True, ondelete="cascade"
    )
    server_template_id = fields.Many2one(
        comodel_name="cx.tower.server.template", index=True, ondelete="cascade"
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_variable_value_variable_rel",
        column1="variable_value_id",
        column2="variable_id",
        string="Variables",
        compute="_compute_variable_ids",
        store=True,
    )
    required = fields.Boolean()

    _sql_constraints = [
        (
            "tower_variable_value_uniq",
            "unique (variable_id, server_id, server_template_id, "
            "plan_line_action_id, is_global)",
            "Variable can be declared only once for the same record!",
        ),
        (
            "unique_variable_value_server",
            "unique (variable_id, server_id)",
            "A variable value cannot be assigned multiple times to the same server!",
        ),
        (
            "unique_variable_value_template",
            "unique (variable_id, server_template_id)",
            (
                "A variable value cannot be assigned multiple"
                " times to the same server template!"
            ),
        ),
        (
            "unique_variable_value_action",
            "unique (variable_id, plan_line_action_id)",
            (
                "A variable value cannot be assigned multiple"
                " times to the same plan line action!"
            ),
        ),
    ]

    @api.depends("option_id", "variable_id.option_ids")
    def _compute_value_char(self):
        """
        Compute the 'value_char' field, which holds the string representation
        of the selected option for the variable.
        """
        for rec in self:
            if rec.variable_id.option_ids and rec.option_id:
                rec.value_char = rec.option_id.value_char
            elif not rec.variable_id.option_ids:
                rec.value_char = rec.value_char or ""
                rec.option_id = None

    @api.onchange("variable_id")
    def _onchange_variable_id(self):
        """
        Reset option_id when variable changes or
        doesn't have options
        """
        for rec in self:
            rec.option_id = False
            if rec.variable_id.option_ids:
                rec.value_char = False

    @api.constrains("is_global", "value_char")
    def _constraint_global_unique(self):
        """Ensure that there is only one global value exist for the same variable

        Hint to devs:
            `unique nulls not distinct (variable_id,server_id,global_id)`
            can be used instead in PG 15.0+
        """
        for rec in self:
            if rec.is_global:
                val_count = self.search_count(
                    [("variable_id", "=", rec.variable_id.id), ("is_global", "=", True)]
                )
                if val_count > 1:
                    # NB: there is a value check in tests for this message.
                    # Update `test_variable_value_toggle_global`
                    # if you modify this message in your code.
                    raise ValidationError(
                        _(
                            "Only one global value can be defined"
                            " for variable '%(var)s'",
                            var=rec.variable_id.name,
                        )
                    )

    @api.depends("value_char")
    def _compute_variable_ids(self):
        """
        Compute variable_ids based on value_char field.
        """
        template_mixin_obj = self.env["cx.tower.template.mixin"]
        for record in self:
            record.variable_ids = template_mixin_obj._prepare_variable_commands(
                ["value_char"], force_record=record
            )

    def _inverse_value_char(self):
        """Set option_id based on value_char"""
        for rec in self:
            if rec.variable_type == "o" and (
                not rec.option_id or rec.option_id.value_char != rec.value_char
            ):
                option = rec.variable_id.option_ids.filtered(
                    lambda x, v=rec.value_char: x.value_char == v
                )
                if option:
                    rec.option_id = option.id
                else:
                    raise ValidationError(
                        _(
                            "Option '%(val)s' is not available for variable '%(var)s'",
                            val=rec.value_char,
                            var=rec.variable_id.name,
                        )
                    )

    def _used_in_models(self):
        """Returns information about models which use this mixin.

        Returns:
            dict(): of the following format:
                {"model.name": ("m2o_field_name", "model_description")}
            Eg:
                {"my.custom.model": ("much_model_id", "Much Model")}
        """
        return {
            "cx.tower.server": ("server_id", "Server"),
            "cx.tower.plan.line.action": ("plan_line_action_id", "Action"),
            "cx.tower.server.template": ("server_template_id", "Server Template"),
        }

    def _check_is_global(self):
        """
        This is a helper function used to define
         which variables are considered 'Global'
        Override it to implement your custom logic.

        Returns:
            bool:  True if global else False
        """

        self.ensure_one()
        is_global = True

        # Get m2o field values for all models that use variables.
        # If none of them is set such value is considered 'global'.
        for related_model_info in self._used_in_models().values():
            m2o_field = related_model_info[0]
            if self[m2o_field]:
                is_global = False
                break
        return is_global

    @api.depends("server_id", "server_template_id", "plan_line_action_id")
    def _compute_is_global(self):
        """
        If variable considered `global` when it's not linked to any record.
        """
        for rec in self:
            rec.is_global = rec._check_is_global()

    def _inverse_is_global(self):
        """Triggered when `is_global` is updated"""
        global_values = self.filtered("is_global")
        if global_values:
            values_to_set = {}

            # Set m2o fields related to variable using models to 'False'
            for related_model_info in self._used_in_models().values():
                m2o_field = related_model_info[0]
                values_to_set.update({m2o_field: False})
            global_values.write(values_to_set)

        # Check if we are trying to remove 'global' from value
        #  that doesn't belong to any record.
        record_related_values = self - global_values
        for record in record_related_values:
            if record._check_is_global():
                # NB: there is a value check in tests for this message.
                # Update `test_variable_value_toggle_global` if you modify this message.
                raise ValidationError(
                    _(
                        "Cannot change 'global' status for "
                        "'%(var)s' with value '%(val)s'."
                        "\nTry to assigns it to a record instead.",
                        var=record.variable_id.name,
                        val=record.value_char,
                    )
                )

    def get_by_variable_reference(
        self,
        variable_reference,
        server_id=None,
        server_template_id=None,
        check_global=True,
    ):
        """Get record based on its reference.

        Important: references are case sensitive!

        Args:
            variable_reference (Char): variable reference
            server_reference (Int): Server ID
            server_template_reference (Int): Server template ID

        Returns:
            Dict: Variable values that match provided reference
        """

        domain = [("variable_reference", "=", variable_reference)]
        # Server or server template specific
        if server_id:
            domain.append(("server_id", "=", server_id))
        elif server_template_id:
            domain.append(("server_template_id", "=", server_template_id))

        if check_global:
            domain = OR(
                [
                    domain,
                    [
                        ("variable_reference", "=", variable_reference),
                        ("is_global", "=", True),
                    ],
                ]
            )

        search_result = self.search(domain)
        result = {}
        if search_result:
            if server_id:
                value_char = search_result.filtered("server_id").mapped("value_char")
                result.update(
                    {"server": value_char and value_char[0] if value_char else None}
                )
            if server_template_id:
                value_char = search_result.filtered("server_template_id").mapped(
                    "value_char"
                )
                result.update(
                    {
                        "server_template": value_char and value_char[0]
                        if value_char
                        else None
                    }
                )
            if check_global:
                value_char = search_result.filtered("is_global").mapped("value_char")
                result.update(
                    {"global": value_char and value_char[0] if value_char else None}
                )

        return result

    @api.constrains("server_id", "server_template_id", "plan_line_action_id")
    def _check_single_assignment(self):
        """Ensure that a variable is only assigned to one model at a time."""
        for record in self:
            # Check how many of the fields are set
            count_assigned = (
                bool(record.server_id)
                + bool(record.server_template_id)
                + bool(record.plan_line_action_id)
            )
            if count_assigned > 1:
                raise ValidationError(
                    _(
                        "Variable '%(var)s' can only be assigned to one of the models "
                        "at a time: "
                        "Server, Server Template, or Plan Line Action.",
                        var=record.variable_id.name,
                    )
                )

    # Check cx.tower.reference.mixin for the function documentation
    def _get_pre_populated_model_data(self):
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.variable.value": ["cx.tower.variable", "variable_id"]})
        return res
