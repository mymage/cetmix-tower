# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerServerTemplateCreateWizard(models.TransientModel):
    """Create new server from template"""

    _name = "cx.tower.server.template.create.wizard"
    _description = "Create new server from template"

    server_template_id = fields.Many2one(
        "cx.tower.server.template",
        string="Server Template",
        readonly=True,
    )
    name = fields.Char(
        string="Server Name",
        required=True,
    )
    color = fields.Integer(help="For better visualization in views")
    ip_v4_address = fields.Char(string="IPv4 Address")
    ip_v6_address = fields.Char(string="IPv6 Address")
    ssh_port = fields.Char(string="SSH port", default="22")
    ssh_username = fields.Char(
        string="SSH Username",
        required=True,
        help="This is required, however you can change this later "
        "in the server settings",
    )
    ssh_password = fields.Char(string="SSH Password")
    ssh_key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="SSH Private Key",
        domain=[("key_type", "=", "k")],
    )
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
        default="p",
        required=True,
    )
    line_ids = fields.One2many(
        comodel_name="cx.tower.server.template.create.wizard.line",
        inverse_name="wizard_id",
        string="Configuration Variables",
    )
    has_missing_required_values = fields.Boolean(
        compute="_compute_has_missing_required_values",
    )
    missing_required_variables = fields.Text(
        compute="_compute_missing_required_variables_message",
    )
    missing_required_variables_message = fields.Text(
        compute="_compute_missing_required_variables_message",
    )

    @api.depends("line_ids.value_char", "line_ids.required")
    def _compute_has_missing_required_values(self):
        """
        Compute whether there are required variables with missing values.
        """
        for wizard in self:
            missing_vars = wizard.line_ids.filtered(
                lambda line: line.required and not line.value_char
            )
            wizard.has_missing_required_values = bool(missing_vars)
            wizard.missing_required_variables = ", ".join(
                missing_vars.mapped("variable_id.name")
            )

    @api.depends("has_missing_required_values")
    def _compute_missing_required_variables_message(self):
        """
        Computes the user-friendly message for missing required variables.
        """
        for wizard in self:
            if wizard.has_missing_required_values and wizard.missing_required_variables:
                wizard.missing_required_variables_message = _(
                    "Please provide values for the following "
                    "configuration variables: %(variables)s",
                    variables=wizard.missing_required_variables,
                )
            else:
                wizard.missing_required_variables_message = False

    def _prepare_server_parameters(self):
        """Prepare new server parameters

        Returns:
            dict(): New server parameters
        """
        res = {
            "ip_v4_address": self.ip_v4_address,
            "ip_v6_address": self.ip_v6_address,
            "ssh_port": self.ssh_port,
            "ssh_username": self.ssh_username,
            "ssh_password": self.ssh_password,
            "ssh_key_id": self.ssh_key_id.id,
            "ssh_auth_mode": self.ssh_auth_mode,
        }
        if self.line_ids:
            res.update(
                {
                    "configuration_variables": {
                        line.variable_reference: line.value_char
                        for line in self.line_ids
                    }
                }
            )
        return res

    def action_confirm(self):
        """
        Create and open new created server from template
        """
        self.ensure_one()

        if self.has_missing_required_values:
            raise ValidationError(self.missing_required_variables_message)

        kwargs = self._prepare_server_parameters()
        server = self.server_template_id._create_new_server(self.name, **kwargs)
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_server"
        )
        action.update(
            {"view_mode": "form", "res_id": server.id, "views": [(False, "form")]}
        )
        return action


class CxTowerServerTemplateCreateWizardVariableLine(models.TransientModel):
    """Configuration variables"""

    _name = "cx.tower.server.template.create.wizard.line"
    _description = "Create new server from template variables"

    wizard_id = fields.Many2one("cx.tower.server.template.create.wizard")
    variable_id = fields.Many2one(comodel_name="cx.tower.variable", required=True)
    variable_reference = fields.Char(related="variable_id.reference", readonly=True)
    value_char = fields.Char(string="Value")
    required = fields.Boolean(
        help="Indicates if this variable is mandatory for server creation",
    )
