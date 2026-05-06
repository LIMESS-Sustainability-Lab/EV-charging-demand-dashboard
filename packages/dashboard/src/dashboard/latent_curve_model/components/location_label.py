import dash_mantine_components as dmc

from ..forms import FormModel


def LocationLabel(label: str, form: FormModel):
    return dmc.Group(
        [
            dmc.Badge(label, size="lg", variant="filled"),
            dmc.Text(
                f"lat {form.loc.location.lat:.4f}  ·  "
                f"lng {form.loc.location.lng:.4f}",
                size="sm",
                c="gray",
                style={"fontFamily": "monospace"},
            ),
            dmc.Text(
                f"{form.time.weekday}s · {form.time.month} · {form.time.year}"
                f"  ·  {form.charger.charging_type}",
                size="sm",
                c="gray",
            ),
        ],
        gap="sm",
        wrap="wrap",
    )
