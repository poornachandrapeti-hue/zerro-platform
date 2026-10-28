"""Built-in catalogue attribute templates. Additive to existing procurement item master.

Templates are defaults, not a replacement for approved project design specifications.
"""
from fastapi import HTTPException

TEMPLATES = {'Civil': {'Concrete': ['grade', 'aggregate_size_mm', 'slump_mm', 'cement_type'], 'Reinforcement': ['steel_grade', 'diameter_mm', 'length_m', 'standard'], 'Structural Steel': ['section', 'steel_grade', 'thickness_mm', 'coating'], 'Masonry': ['block_type', 'dimensions_mm', 'compressive_strength_mpa']}, 'Mechanical': {'Pumps': ['flow_m3_hr', 'head_m', 'power_kw', 'fluid', 'seal_type'], 'Motors': ['power_kw', 'voltage_v', 'frequency_hz', 'speed_rpm', 'ip_rating'], 'Couplings': ['bore_mm', 'coupling_type', 'material'], 'Static Equipment': ['volume_m3', 'design_pressure_bar', 'design_temperature_c', 'material']}, 'Electrical': {'Power Cables': ['voltage_grade', 'conductor', 'cores', 'cross_section_mm2', 'insulation'], 'Switchgear': ['rated_current_a', 'voltage_v', 'breaking_capacity_ka', 'poles'], 'Transformers': ['rating_kva', 'hv_kv', 'lv_kv', 'vector_group'], 'Lighting': ['power_w', 'ip_rating', 'lumens']}, 'Instrumentation': {'Pressure Instruments': ['range', 'accuracy_percent', 'output_signal', 'process_connection'], 'Temperature Instruments': ['sensor_type', 'range', 'sheath_material', 'output_signal'], 'Flow Instruments': ['flow_range', 'nominal_size', 'output_signal'], 'Control Valves': ['nominal_size', 'pressure_class', 'cv', 'fail_position']}, 'Piping': {'Pipes': ['nps', 'schedule', 'material_grade', 'end_type'], 'Fittings': ['fitting_type', 'nps', 'schedule', 'material_grade'], 'Flanges': ['nps', 'pressure_class', 'facing', 'material_grade'], 'Valves': ['valve_type', 'nps', 'pressure_class', 'body_material']}, 'Painting': {'Primers': ['coating_type', 'dft_microns', 'mixing_ratio', 'substrate'], 'Intermediate Coats': ['coating_type', 'dft_microns', 'recoat_window'], 'Topcoats': ['finish', 'ral_colour', 'dft_microns', 'gloss'], 'Surface Preparation': ['abrasive_type', 'grit_size', 'preparation_grade']}, 'Structural': {'Steel Sections': ['section', 'grade', 'length_m', 'coating']}, 'HVAC': {'Air Handling Units': ['airflow_m3_hr', 'cooling_capacity_kw', 'static_pressure_pa']}, 'Fire Protection': {'Sprinklers': ['k_factor', 'temperature_rating_c', 'connection_size']}, 'Insulation': {'Thermal Insulation': ['density_kg_m3', 'thickness_mm', 'thermal_conductivity']}, 'Refractory': {'Castable': ['service_temperature_c', 'density_kg_m3', 'chemistry']}, 'Welding': {'Electrodes': ['classification', 'diameter_mm', 'welding_process']}}

# Additional discipline families share the existing catalogue and validation API.
# These defaults can be superseded by configurable templates in a later checkpoint.
TEMPLATES.update({
    "Roads & Buildings": {
        "Paving": ["material_type", "grade", "thickness_mm", "application"],
        "Doors & Windows": ["frame_material", "width_mm", "height_mm", "fire_rating"],
    },
    "Telecom / ELV": {
        "Fibre Cables": ["fibre_type", "core_count", "armour", "fire_rating"],
        "CCTV": ["resolution_mp", "lens_mm", "ip_rating", "power_type"],
        "Network Switches": ["port_count", "speed_gbps", "poe_budget_w", "mounting"],
    },
})
TEMPLATES["Civil"].update({
    "Cement": ["cement_type", "grade", "pack_size_kg", "standard"],
    "Aggregates": ["aggregate_type", "nominal_size_mm", "grading", "source"],
    "Waterproofing": ["membrane_type", "thickness_mm", "coverage_m2", "standard"],
    "Grouting": ["grout_type", "compressive_strength_mpa", "working_time_min"],
})
TEMPLATES["Mechanical"].update({
    "Compressors": ["capacity_m3_hr", "pressure_bar", "power_kw", "cooling_method"],
    "Bearings": ["bearing_type", "bore_mm", "load_rating_kn", "part_number"],
    "Gearboxes": ["ratio", "output_torque_nm", "input_speed_rpm", "mounting"],
    "Heat Exchangers": ["duty_kw", "design_pressure_bar", "material", "area_m2"],
})
TEMPLATES["Electrical"].update({
    "Cable Trays": ["material", "width_mm", "height_mm", "thickness_mm"],
    "Earthing": ["material", "section_mm2", "length_m", "coating"],
    "Motor Starters": ["starter_type", "power_kw", "voltage_v", "ip_rating"],
})
TEMPLATES["Instrumentation"].update({
    "Level Instruments": ["technology", "range_m", "process_connection", "output_signal"],
    "PLC Modules": ["module_type", "channel_count", "supply_v", "protocol"],
    "Junction Boxes": ["enclosure_material", "ip_rating", "terminal_count", "hazardous_area_rating"],
})
TEMPLATES["Piping"].update({
    "Gaskets": ["gasket_type", "nps", "pressure_class", "material"],
    "Stud Bolts": ["diameter_mm", "length_mm", "grade", "standard"],
    "Supports": ["support_type", "pipe_size", "load_rating_kn", "material"],
})
TEMPLATES["Painting"].update({
    "Thinners": ["compatible_coating", "pack_size_l", "shelf_life_months"],
    "Abrasives": ["abrasive_type", "grit_size", "purity_percent"],
    "Fireproofing": ["coating_type", "fire_rating_minutes", "dft_microns", "substrate"],
})
TEMPLATES["Structural"].update({"Gratings": ["material", "bar_size", "mesh_size", "load_rating_kn"]})
TEMPLATES["HVAC"].update({
    "Ducting": ["material", "gauge", "width_mm", "height_mm"],
    "Dampers": ["damper_type", "width_mm", "height_mm", "fire_rating_minutes"],
    "Filters": ["filter_class", "airflow_m3_hr", "pressure_drop_pa"],
})
TEMPLATES["Fire Protection"].update({
    "Hydrants": ["hydrant_type", "connection_size", "pressure_rating_bar"],
    "Fire Pumps": ["flow_m3_hr", "head_m", "power_kw", "pump_type"],
})
TEMPLATES["Insulation"].update({"Cladding": ["material", "thickness_mm", "finish"]})
TEMPLATES["Refractory"].update({
    "Firebricks": ["grade", "service_temperature_c", "density_kg_m3", "dimensions_mm"],
    "Ceramic Fibre": ["service_temperature_c", "density_kg_m3", "thickness_mm"],
})
TEMPLATES["Welding"].update({
    "Filler Wire": ["classification", "diameter_mm", "welding_process", "pack_size_kg"],
    "Shielding Gas": ["composition", "purity_percent", "cylinder_size_l"],
})

def list_templates():
    return [{"discipline": d, "categories": [{"name": c, "fields": [{"key": key, "label": key.replace("_", " ").title(), "type": "text", "required": False} for key in fields]} for c, fields in groups.items()]} for d, groups in TEMPLATES.items()]

def validate_attributes(discipline, category, attributes):
    if not isinstance(attributes, dict):
        raise HTTPException(422, "Specifications must be an object")
    fields = TEMPLATES.get(discipline, {}).get(category)
    if fields is None:
        if attributes:
            raise HTTPException(422, "Choose a supported discipline and category for structured specifications")
        return {}
    unknown = set(attributes) - set(fields)
    if unknown:
        raise HTTPException(422, "Unsupported specification fields: " + ", ".join(sorted(unknown)))
    cleaned = {}
    for key, value in attributes.items():
        if not isinstance(value, (str, int, float)) or isinstance(value, bool) or len(str(value)) > 300:
            raise HTTPException(422, "Invalid specification value for " + key)
        cleaned[key] = str(value).strip()
    return cleaned


# The built-in templates above are fallbacks. Organization-specific overrides
# are stored in procurement_specification_templates and never mutate TEMPLATES.
import re

_FIELD_TYPES = {"text", "number", "boolean", "select"}
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def validate_template_fields(fields):
    from fastapi import HTTPException
    if not isinstance(fields, list) or not (1 <= len(fields) <= 60):
        raise HTTPException(422, "Template requires 1 to 60 fields")
    seen = set()
    result = []
    for field in fields:
        if not isinstance(field, dict):
            raise HTTPException(422, "Invalid template field")
        key = field.get("key")
        label = field.get("label")
        kind = field.get("type", "text")
        options = field.get("options", [])
        required = field.get("required", False)
        if not isinstance(key, str) or not _KEY.fullmatch(key) or key in seen:
            raise HTTPException(422, "Invalid or duplicate field key")
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= 100):
            raise HTTPException(422, "Invalid field label")
        if kind not in _FIELD_TYPES or type(required) is not bool:
            raise HTTPException(422, "Invalid field type or required flag")
        if not isinstance(options, list) or len(options) > 100 or any(
            not isinstance(v, str) or not (1 <= len(v) <= 100) for v in options
        ):
            raise HTTPException(422, "Invalid field choices")
        if kind == "select" and not options:
            raise HTTPException(422, "Select field requires choices")
        if kind != "select" and options:
            raise HTTPException(422, "Choices only supported on select fields")
        if len(set(options)) != len(options):
            raise HTTPException(422, "Duplicate field choices")
        seen.add(key)
        result.append({"key": key, "label": label.strip(), "type": kind,
                       "required": required, "options": options})
    return result


def configured_templates(db, organization_id):
    from .models import CatalogueSpecificationTemplate
    groups = {discipline: {category: [
        {"key": k, "label": k.replace("_", " ").title(), "type": "text", "required": False, "options": []}
        for k in keys] for category, keys in categories.items()}
        for discipline, categories in TEMPLATES.items()}
    rows = db.query(CatalogueSpecificationTemplate).filter_by(
        organization_id=organization_id, active=True).all()
    for row in rows:
        groups.setdefault(row.discipline, {})[row.category] = row.fields
    return [{"discipline": d, "categories": [{"name": c, "fields": fields}
            for c, fields in categories.items()]} for d, categories in groups.items()]


def validate_configured_attributes(db, organization_id, discipline, category, attributes):
    from .models import CatalogueSpecificationTemplate
    row = db.query(CatalogueSpecificationTemplate).filter_by(
        organization_id=organization_id, discipline=discipline,
        category=category, active=True).first()
    if row is None:
        return validate_attributes(discipline, category, attributes)
    if not isinstance(attributes, dict):
        raise HTTPException(422, "Specifications must be an object")
    fields = {f["key"]: f for f in row.fields}
    if set(attributes) - set(fields):
        raise HTTPException(422, "Unsupported specification field")
    cleaned = {}
    for key, field in fields.items():
        value = attributes.get(key)
        if value in (None, ""):
            if field["required"]:
                raise HTTPException(422, "Required specification missing: " + key)
            continue
        kind = field["type"]
        if kind == "boolean":
            if type(value) is not bool:
                raise HTTPException(422, "Expected boolean: " + key)
        elif kind == "number":
            if type(value) not in (float, int) or not -1e15 < value < 1e15:
                raise HTTPException(422, "Expected finite number: " + key)
        else:
            if not isinstance(value, str) or len(value) > 300:
                raise HTTPException(422, "Expected text: " + key)
            value = value.strip()
            if kind == "select" and value not in field["options"]:
                raise HTTPException(422, "Invalid choice: " + key)
        cleaned[key] = value
    return cleaned
