"""Discipline activity examples. Checkpoints are not one shared checklist."""

EXAMPLES = {
    "Civil": [
        ("CIV-SURVEY", "Survey", "m", "Quantity", "Control points are available.", "Survey book", ["Benchmark checked", "Coordinates recorded"], "Coordinates are recorded against the control points."),
        ("CIV-EXCAV", "Excavation", "m3", "Quantity", "Survey is recorded.", "Formation photograph", ["Side slopes stable", "Formation inspected"], "Formation level matches the drawing."),
        ("CIV-BACK", "Backfilling", "m3", "Quantity", "Adjacent work is accepted.", "Layer record", ["Material approved", "Layer thickness"], "Backfill reaches the specified level."),
        ("CIV-COMP", "Compaction", "m3", "Quantity", "Backfill layer is placed.", "Density result", ["Layer thickness", "Density result"], "Specified density is recorded for each layer."),
        ("CIV-PILE", "Piling", "no", "Item completion", "Pile layout is released.", "Pile record", ["Pile position", "Driving record"], "Each pile has a position and driving record."),
        ("CIV-REBAR", "Reinforcement", "t", "Quantity", "Bar schedule is current.", "Bar schedule", ["Bar mark", "Cover checked"], "Bars match the schedule and cover."),
        ("CIV-FORM", "Formwork", "m2", "Quantity", "Line and level are set.", "Formwork check", ["Line and level", "Release oil"], "Formwork is stable and at the required line."),
        ("CIV-CONC", "Concreting", "m3", "Quantity", "Formwork and reinforcement are accepted.", "Pour record", ["Slump recorded", "Pour card signed"], "The pour record and slump are filed."),
    ],
    "Mechanical": [
        ("MEC-PLACE", "Equipment placement", "no", "Item completion", "Foundation is accepted.", "Setting-out mark", ["Foundation accepted", "Orientation marked"], "Equipment sits on the marked orientation."),
        ("MEC-ALIGN", "Alignment", "mm", "Quantity", "Equipment is placed.", "Alignment sheet", ["Dial readings", "Shim record"], "Alignment readings are within the sheet."),
        ("MEC-GROUT", "Grouting", "m3", "Quantity", "Alignment is recorded.", "Grout record", ["Surface clean", "Grout cubes"], "Grout record and cubes are filed."),
        ("MEC-INST", "Installation", "no", "Item completion", "Grout is accepted where required.", "Torque record", ["Hold-down bolts", "Torque record"], "Hold-down bolts are torqued."),
        ("MEC-TEST", "Testing", "no", "Item completion", "Installation is complete.", "Run-in sheet", ["Run-in sheet", "No leak at joint"], "The run-in sheet is signed."),
    ],
    "Electrical": [
        ("ELE-TRAY", "Cable tray installation", "m", "Quantity", "Route is released.", "Support record", ["Support spacing", "Earthing bond"], "Tray route and bonds match the drawing."),
        ("ELE-LAY", "Cable laying", "m", "Quantity", "Tray or trench is ready.", "Drum record", ["Drum number", "Route checked"], "Drum number and route are recorded."),
        ("ELE-TERM", "Termination", "no", "Item completion", "Cable is laid.", "Termination card", ["Gland fitted", "Core mark"], "Gland and core marks are recorded."),
        ("ELE-EARTH", "Earthing", "no", "Item completion", "Earth pit or grid is accessible.", "Resistance reading", ["Electrode identified", "Resistance reading"], "Resistance reading is filed."),
        ("ELE-EQ", "Equipment installation", "no", "Item completion", "Plinth or frame is accepted.", "Nameplate photo", ["Nameplate recorded", "Fixings checked"], "Nameplate matches the equipment list."),
        ("ELE-TEST", "Testing", "no", "Item completion", "Terminations are complete.", "IR test", ["IR test", "Circuit identity"], "Insulation resistance is recorded."),
    ],
    "Instrumentation": [
        ("INS-INST", "Instrument installation", "no", "Item completion", "Hook-up is released.", "Tag check", ["Tag match", "Hook-up used"], "Tag matches the hook-up."),
        ("INS-TUBE", "Tubing", "m", "Quantity", "Instrument is installed.", "Tubing sheet", ["Slope checked", "Leak check"], "Slope and leak check are recorded."),
        ("INS-WIRE", "Wiring", "m", "Quantity", "Instrument is installed.", "Pair list", ["Pair mark", "Gland fitted"], "Pair marks match the loop sheet."),
        ("INS-CAL", "Calibration", "no", "Item completion", "Instrument is installed.", "Calibration sheet", ["As-found", "As-left"], "As-found and as-left are filed."),
        ("INS-LOOP", "Loop checks", "no", "Item completion", "Calibration is filed.", "Loop sheet", ["Loop sheet", "End-to-end result"], "The loop sheet is signed."),
    ],
    "Piping": [
        ("PIP-FAB", "Fabrication", "spool", "Item completion", "Spool drawing is released.", "Weld map", ["Spool drawing", "Weld map"], "Spool identity matches the weld map."),
        ("PIP-FIT", "Fit-up", "no", "Item completion", "Spool is fabricated.", "Fit-up report", ["Gap checked", "Alignment checked"], "Gap and alignment are recorded."),
        ("PIP-WELD", "Welding", "no", "Item completion", "Fit-up is accepted.", "Weld record", ["WPS named", "Welder id"], "WPS and welder are recorded."),
        ("PIP-NDT", "NDT", "no", "Item completion", "Weld is complete.", "NDT report", ["Film or record", "Report number"], "NDT report number is filed."),
        ("PIP-REL", "Spool release", "no", "Item completion", "Required NDT is accepted.", "Release stamp", ["NDT accepted", "Release stamp"], "Release stamp is on the spool."),
        ("PIP-ERECT", "Erection", "no", "Item completion", "Spool is released.", "Erection check", ["Support checked", "Orientation checked"], "Support and orientation match the drawing."),
        ("PIP-TEST", "Pressure testing", "no", "Item completion", "Test pack is approved.", "Pressure chart", ["Test pack", "Pressure chart"], "Pressure chart is filed with the test pack."),
    ],
}


def example_rows(discipline_name):
    rows = []
    for code, name, unit, method, prerequisites, evidence, checkpoints, completion in EXAMPLES.get(
        discipline_name, []
    ):
        rows.append(
            {
                "code": code,
                "name": name,
                "unit": unit,
                "progress_method": method,
                "prerequisites": prerequisites,
                "required_evidence": evidence,
                "checkpoints": checkpoints,
                "completion_conditions": completion,
            }
        )
    return rows
