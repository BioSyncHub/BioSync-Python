from pathlib import Path


PREFERRED_MODEL_PROFILES = ("BioSync-Warzone", "BioSync-Fortnite")
LEGACY_MODEL_PROFILE_NAMES = {
    "ggwarzone": "BioSync-Warzone",
    "ggmwarzone": "BioSync-Warzone",
    "biosync": "BioSync-Fortnite",
    "biosync-ai": "BioSync-Fortnite",
}


def discover_model_profiles(models_dir: Path) -> dict[str, Path]:
    model_paths = {
        model_path.stem: model_path
        for model_path in models_dir.glob("*.onnx")
        if model_path.is_file()
    }
    profile_order = {
        profile_name: index
        for index, profile_name in enumerate(PREFERRED_MODEL_PROFILES)
    }
    return dict(sorted(
        model_paths.items(),
        key=lambda item: (
            profile_order.get(item[0], len(profile_order)),
            item[0].casefold(),
        ),
    ))


def normalize_model_profile_path(model_path: str) -> str:
    path = Path(model_path)
    profile_name = LEGACY_MODEL_PROFILE_NAMES.get(path.stem.casefold())
    if profile_name is None:
        return model_path
    return str(Path("models") / f"{profile_name}.onnx")
