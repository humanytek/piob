from odoo import models


class StockMove(models.Model):
    _inherit = 'stock.move'

    def write(self, vals):
        """
        When move_line_ids are written with ORM delete commands (2 = unlink,
        6 = replace-all), inject the barcode-app context so that
        StockMoveLine.unlink() does not block the cascaded deletions.

        This covers the serial-number-generation wizard path:
          1. User opens "Detailed Operations" for a serialised product.
          2. The "Generate Serials" wizard returns new line values.
          3. The form saves via `stock.move.web_save`, which sends ORM commands
             such as (2, old_line_id) to delete the previous placeholder line.
          4. That placeholder may have picked=True / captured_by_barcode=True
             from prior barcode scanning, which would otherwise trigger our
             StockMoveLine.unlink() guard.

        Only applied for supervisors and admins; operators cannot reach this
        form-level flow from the UI.
        """
        if 'move_line_ids' in vals:
            has_delete_cmd = any(
                isinstance(cmd, (list, tuple)) and len(cmd) >= 1 and cmd[0] in (2, 6)
                for cmd in vals['move_line_ids']
            )
            if has_delete_cmd and (
                self.env.su
                or self.env.user.has_group(
                    'alx_stock_transfer_control.group_stock_logistics_supervisor'
                )
            ):
                return super(
                    StockMove, self.with_context(from_barcode_app=True)
                ).write(vals)
        return super().write(vals)

    def post_barcode_process(self, barcode_quantities):
        """
        Inject the barcode-app context flag before delegating to the standard
        implementation.

        `post_barcode_process` is called by the barcode app via a plain
        `call_kw` request — it does NOT go through our custom
        `/stock_barcode/save_barcode_data` controller, so the
        `from_barcode_app` context flag is never set automatically.

        Without the flag, the internal `unlink()` calls inside
        `split_uncompleted_moves()` (which clean up zero-quantity / orphan
        move lines as part of normal barcode processing) are blocked by our
        `StockMoveLine.unlink()` guard, causing a visible error whenever a
        user navigates away from or saves in the Barcode App.
        """
        return super(
            StockMove, self.with_context(from_barcode_app=True)
        ).post_barcode_process(barcode_quantities)
