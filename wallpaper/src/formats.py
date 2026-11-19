FORMATS = {
    "3840x2160":  (3840, 2160, dict(f=1.00, cx=0.500, cy=0.600)),
    "3456x2160":  (3456, 2160, dict(f=1.00, cx=0.518, cy=0.600)),
    "5120x2160":  (5120, 2160, dict(f=1.00, cx=0.500, cy=0.560)),
    "2160x2160":  (2160, 2160, dict(f=0.80, cx=0.640, cy=0.440)),
    "1290x2796":  (1290, 2796, dict(f=0.70, cx=0.840, cy=0.530)),
    "1500x500":   (1500,  500, dict(f=1.25, cx=0.520, cy=0.480)),
}

# light-only overrides: in the light theme the lower frame is mist, so tall frames lower the
# camera to keep the solid mist band to ~12% of the height (dark ground there is textured, light mist isn't)
FORMATS_LIGHT = dict(FORMATS)
FORMATS_LIGHT["2160x2160"] = (2160, 2160, dict(f=0.80, cx=0.640, cy=0.640))
FORMATS_LIGHT["1290x2796"] = (1290, 2796, dict(f=0.70, cx=0.840, cy=0.660))
