DEFAULT_VIEW_SETTINGS = {
    "show_fov": True,
    "fov_color": "#32D7A0",
    "overlay_opacity": 85,
    "esp_enabled": False,
    "esp_style": "Normal",
    "esp_thickness": 2,
    "esp_color": "#FF3030",
    "esp_opacity": 45,
    "distance_filter": False,
    "min_distance": 0.0,
    "max_distance": 1.0,
    "min_confidence": 0.55,
    "iou_threshold": 0.45,
    "max_detections": 5,
    "ignore_small_targets": False,
    "min_box_area": 0.002,
    "ignore_large_targets": False,
    "max_box_area": 0.8,
    "snap_line": False,
    "snap_line_color": "#32D7A0",
    "snap_line_thickness": 2,
    "show_aim_marker": True,
    "marker_color": "#FF3030",
    "show_body_zones": False,
    "head_color": "#F06464",
    "chest_color": "#32C7D7",
    "belly_color": "#F2C94C",
}


def merge_view_settings(settings):
    return {**DEFAULT_VIEW_SETTINGS, **settings}
