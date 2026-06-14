import re
import math
from base64 import b64encode
from urllib.parse import quote
import zlib

_URI_SAFE = "-_.!~*'()"


def tokenize_path(d):
    return re.findall(
        r'[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',
        d or ''
    )


def _arc_to_bezier(x1, y1, rx, ry, phi_deg, large_arc, sweep, x2, y2):
    """
    Convert one SVG arc segment to a list of cubic Bezier curves.
    Returns list of (cx1, cy1, cx2, cy2, ex, ey).
    Implements the algorithm from the SVG 1.1 spec appendix F.
    """
    if x1 == x2 and y1 == y2:
        return []
    if rx == 0 or ry == 0:
        return [(x1, y1, x2, y2, x2, y2)]

    phi = math.radians(phi_deg % 360)
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p = cos_phi * dx + sin_phi * dy
    y1p = -sin_phi * dx + cos_phi * dy

    rx, ry = abs(rx), abs(ry)
    x1p_sq, y1p_sq = x1p * x1p, y1p * y1p
    rx_sq, ry_sq = rx * rx, ry * ry

    lam = x1p_sq / rx_sq + y1p_sq / ry_sq
    if lam > 1:
        lam = math.sqrt(lam)
        rx *= lam
        ry *= lam
        rx_sq = rx * rx
        ry_sq = ry * ry

    num = max(0.0, rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq)
    den = rx_sq * y1p_sq + ry_sq * x1p_sq
    sq = math.sqrt(num / den) if den else 0.0
    if large_arc == sweep:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle_between(ux, uy, vx, vy):
        n = math.sqrt(ux * ux + uy * uy) * math.sqrt(vx * vx + vy * vy)
        if n == 0:
            return 0.0
        c = max(-1.0, min(1.0, (ux * vx + uy * vy) / n))
        a = math.acos(c)
        return -a if ux * vy - uy * vx < 0 else a

    theta1 = angle_between(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle_between(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry,
    )
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    n_segs = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2))))
    dt = dtheta / n_segs
    curves = []
    t = theta1
    for _ in range(n_segs):
        half = dt / 2
        alpha = math.sin(dt) * (math.sqrt(4 + 3 * math.tan(half) ** 2) - 1) / 3
        ct, st = math.cos(t), math.sin(t)
        ct2, st2 = math.cos(t + dt), math.sin(t + dt)
        ex = cx + rx * cos_phi * ct - ry * sin_phi * st
        ey = cy + rx * sin_phi * ct + ry * cos_phi * st
        fx = cx + rx * cos_phi * ct2 - ry * sin_phi * st2
        fy = cy + rx * sin_phi * ct2 + ry * cos_phi * st2
        d1x = -rx * cos_phi * st - ry * sin_phi * ct
        d1y = -rx * sin_phi * st + ry * cos_phi * ct
        d2x = -rx * cos_phi * st2 - ry * sin_phi * ct2
        d2y = -rx * sin_phi * st2 + ry * cos_phi * ct2
        curves.append((
            ex + alpha * d1x, ey + alpha * d1y,
            fx - alpha * d2x, fy - alpha * d2y,
            fx, fy,
        ))
        t += dt
    return curves


def path_points(d):
    """Yield approximate (x, y) key-points from SVG path data (used for bounding box)."""
    tokens = tokenize_path(d)
    i, cx, cy = 0, 0.0, 0.0
    sx, sy = 0.0, 0.0
    lc_x, lc_y = None, None

    while i < len(tokens):
        tok = tokens[i]
        if tok not in 'MmLlHhVvCcSsQqTtAaZz':
            i += 1
            continue
        cmd, i = tok, i + 1
        if cmd in 'Zz':
            cx, cy = sx, sy
            continue
        while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
            try:
                if cmd in 'ML':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    yield cx, cy
                    i += 2
                    if cmd == 'M':
                        sx, sy = cx, cy
                        cmd = 'L'
                    lc_x = lc_y = None
                elif cmd in 'ml':
                    cx, cy = cx + float(tokens[i]), cy + float(tokens[i+1])
                    yield cx, cy
                    i += 2
                    if cmd == 'm':
                        sx, sy = cx, cy
                        cmd = 'l'
                    lc_x = lc_y = None
                elif cmd == 'H':
                    cx = float(tokens[i])
                    yield cx, cy
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'h':
                    cx += float(tokens[i])
                    yield cx, cy
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'V':
                    cy = float(tokens[i])
                    yield cx, cy
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'v':
                    cy += float(tokens[i])
                    yield cx, cy
                    i += 1
                    lc_x = lc_y = None
                elif cmd in 'Cc':
                    bx, by = (0.0, 0.0) if cmd == 'C' else (cx, cy)
                    x1, y1 = bx + float(tokens[i]), by + float(tokens[i+1])
                    x2, y2 = bx + float(tokens[i+2]), by + float(tokens[i+3])
                    cx, cy = bx + float(tokens[i+4]), by + float(tokens[i+5])
                    yield x1, y1
                    yield x2, y2
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 6
                elif cmd in 'Ss':
                    bx, by = (0.0, 0.0) if cmd == 'S' else (cx, cy)
                    rx1 = 2 * cx - lc_x if lc_x is not None else cx
                    ry1 = 2 * cy - lc_y if lc_y is not None else cy
                    x2 = bx + float(tokens[i])
                    y2 = by + float(tokens[i+1])
                    cx = bx + float(tokens[i+2])
                    cy = by + float(tokens[i+3])
                    yield rx1, ry1
                    yield x2, y2
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 4
                elif cmd in 'Qq':
                    bx, by = (0.0, 0.0) if cmd == 'Q' else (cx, cy)
                    qx1 = bx + float(tokens[i])
                    qy1 = by + float(tokens[i+1])
                    cx = bx + float(tokens[i+2])
                    cy = by + float(tokens[i+3])
                    yield qx1, qy1
                    yield cx, cy
                    lc_x, lc_y = qx1, qy1
                    i += 4
                elif cmd in 'Tt':
                    qx1 = 2 * cx - lc_x if lc_x is not None else cx
                    qy1 = 2 * cy - lc_y if lc_y is not None else cy
                    if cmd == 'T':
                        cx, cy = float(tokens[i]), float(tokens[i+1])
                    else:
                        cx, cy = cx + float(tokens[i]), cy + float(tokens[i+1])
                    yield qx1, qy1
                    yield cx, cy
                    lc_x, lc_y = qx1, qy1
                    i += 2
                elif cmd in 'Aa' and i + 6 < len(tokens):
                    bx, by = cx, cy
                    rx_a, ry_a = abs(float(tokens[i])), abs(float(tokens[i+1]))
                    phi_a = float(tokens[i+2])
                    la, sw = int(float(tokens[i+3])), int(float(tokens[i+4]))
                    if cmd == 'A':
                        cx, cy = float(tokens[i+5]), float(tokens[i+6])
                    else:
                        cx, cy = bx + float(tokens[i+5]), by + float(tokens[i+6])
                    for bz in _arc_to_bezier(bx, by, rx_a, ry_a, phi_a, la, sw, cx, cy):
                        yield bz[4], bz[5]
                    lc_x = lc_y = None
                    i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1


def sample_open_path(d):
    """
    Yield on-curve (x, y) points from an open SVG path for draw.io edge waypoints.
    Unlike path_points, this yields actual points ON the curve (midpoints for bezier
    segments), not off-curve control points.
    """
    def _cubic_mid(x0, y0, x1, y1, x2, y2, x3, y3):
        return (0.125*x0 + 0.375*x1 + 0.375*x2 + 0.125*x3,
                0.125*y0 + 0.375*y1 + 0.375*y2 + 0.125*y3)

    tokens = tokenize_path(d)
    i, cx, cy = 0, 0.0, 0.0
    sx, sy = 0.0, 0.0
    lc_x, lc_y = None, None

    while i < len(tokens):
        tok = tokens[i]
        if tok not in 'MmLlHhVvCcSsQqTtAaZz':
            i += 1
            continue
        cmd, i = tok, i + 1

        if cmd in 'Zz':
            cx, cy = sx, sy
            continue

        while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
            try:
                if cmd == 'M':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    sx, sy = cx, cy
                    yield cx, cy
                    cmd = 'L'
                    lc_x = lc_y = None
                    i += 2
                elif cmd == 'm':
                    cx, cy = cx + float(tokens[i]), cy + float(tokens[i+1])
                    sx, sy = cx, cy
                    yield cx, cy
                    cmd = 'l'
                    lc_x = lc_y = None
                    i += 2
                elif cmd == 'L':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 2
                elif cmd == 'l':
                    cx += float(tokens[i])
                    cy += float(tokens[i+1])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 2
                elif cmd == 'H':
                    cx = float(tokens[i])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 1
                elif cmd == 'h':
                    cx += float(tokens[i])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 1
                elif cmd == 'V':
                    cy = float(tokens[i])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 1
                elif cmd == 'v':
                    cy += float(tokens[i])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 1
                elif cmd == 'C':
                    x1, y1 = float(tokens[i]), float(tokens[i+1])
                    x2, y2 = float(tokens[i+2]), float(tokens[i+3])
                    nx, ny = float(tokens[i+4]), float(tokens[i+5])
                    yield _cubic_mid(cx, cy, x1, y1, x2, y2, nx, ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 6
                elif cmd == 'c':
                    x1, y1 = cx + float(tokens[i]), cy + float(tokens[i+1])
                    x2, y2 = cx + float(tokens[i+2]), cy + float(tokens[i+3])
                    nx, ny = cx + float(tokens[i+4]), cy + float(tokens[i+5])
                    yield _cubic_mid(cx, cy, x1, y1, x2, y2, nx, ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 6
                elif cmd == 'S':
                    rx1 = 2*cx - lc_x if lc_x is not None else cx
                    ry1 = 2*cy - lc_y if lc_y is not None else cy
                    x2, y2 = float(tokens[i]), float(tokens[i+1])
                    nx, ny = float(tokens[i+2]), float(tokens[i+3])
                    yield _cubic_mid(cx, cy, rx1, ry1, x2, y2, nx, ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 4
                elif cmd == 's':
                    rx1 = 2*cx - lc_x if lc_x is not None else cx
                    ry1 = 2*cy - lc_y if lc_y is not None else cy
                    x2, y2 = cx + float(tokens[i]), cy + float(tokens[i+1])
                    nx, ny = cx + float(tokens[i+2]), cy + float(tokens[i+3])
                    yield _cubic_mid(cx, cy, rx1, ry1, x2, y2, nx, ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = x2, y2
                    i += 4
                elif cmd == 'Q':
                    qx, qy = float(tokens[i]), float(tokens[i+1])
                    nx, ny = float(tokens[i+2]), float(tokens[i+3])
                    yield (0.25*cx + 0.5*qx + 0.25*nx, 0.25*cy + 0.5*qy + 0.25*ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = qx, qy
                    i += 4
                elif cmd == 'q':
                    qx, qy = cx + float(tokens[i]), cy + float(tokens[i+1])
                    nx, ny = cx + float(tokens[i+2]), cy + float(tokens[i+3])
                    yield (0.25*cx + 0.5*qx + 0.25*nx, 0.25*cy + 0.5*qy + 0.25*ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = qx, qy
                    i += 4
                elif cmd == 'T':
                    qx = 2*cx - lc_x if lc_x is not None else cx
                    qy = 2*cy - lc_y if lc_y is not None else cy
                    nx, ny = float(tokens[i]), float(tokens[i+1])
                    yield (0.25*cx + 0.5*qx + 0.25*nx, 0.25*cy + 0.5*qy + 0.25*ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = qx, qy
                    i += 2
                elif cmd == 't':
                    qx = 2*cx - lc_x if lc_x is not None else cx
                    qy = 2*cy - lc_y if lc_y is not None else cy
                    nx, ny = cx + float(tokens[i]), cy + float(tokens[i+1])
                    yield (0.25*cx + 0.5*qx + 0.25*nx, 0.25*cy + 0.5*qy + 0.25*ny)
                    cx, cy = nx, ny
                    yield cx, cy
                    lc_x, lc_y = qx, qy
                    i += 2
                elif cmd in 'Aa' and i + 6 < len(tokens):
                    bx, by = cx, cy
                    rx_a, ry_a = abs(float(tokens[i])), abs(float(tokens[i+1]))
                    phi_a = float(tokens[i+2])
                    la, sw = int(float(tokens[i+3])), int(float(tokens[i+4]))
                    if cmd == 'A':
                        cx, cy = float(tokens[i+5]), float(tokens[i+6])
                    else:
                        cx, cy = bx + float(tokens[i+5]), by + float(tokens[i+6])
                    bzs = _arc_to_bezier(bx, by, rx_a, ry_a, phi_a, la, sw, cx, cy)
                    if bzs:
                        prev = (bx, by)
                        for bz in bzs:
                            yield _cubic_mid(prev[0], prev[1], bz[0], bz[1], bz[2], bz[3], bz[4], bz[5])
                            prev = (bz[4], bz[5])
                    yield cx, cy
                    lc_x = lc_y = None
                    i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1


def path_commands(d, point_transform=None):
    """
    Parse SVG path data into draw.io-style commands with absolute coordinates.
    Arc segments are converted to cubic Beziers so affine transforms can be
    applied directly to their control points.
    """
    def tp(x, y):
        return point_transform(x, y) if point_transform else (x, y)

    commands = []
    tokens = tokenize_path(d)
    i, cx, cy = 0, 0.0, 0.0
    sx, sy = 0.0, 0.0
    lc_x, lc_y = None, None

    while i < len(tokens):
        tok = tokens[i]
        if tok not in 'MmLlHhVvCcSsQqTtAaZz':
            i += 1
            continue
        cmd, i = tok, i + 1
        if cmd in 'Zz':
            commands.append(('close', ()))
            cx, cy = sx, sy
            continue
        while i < len(tokens) and tokens[i] not in 'MmLlHhVvCcSsQqTtAaZz':
            try:
                if cmd == 'M':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    sx, sy = cx, cy
                    commands.append(('move', (tp(cx, cy),)))
                    i += 2
                    cmd = 'L'
                    lc_x = lc_y = None
                elif cmd == 'm':
                    cx, cy = cx + float(tokens[i]), cy + float(tokens[i+1])
                    sx, sy = cx, cy
                    commands.append(('move', (tp(cx, cy),)))
                    i += 2
                    cmd = 'l'
                    lc_x = lc_y = None
                elif cmd == 'L':
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 2
                    lc_x = lc_y = None
                elif cmd == 'l':
                    cx += float(tokens[i])
                    cy += float(tokens[i+1])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 2
                    lc_x = lc_y = None
                elif cmd == 'H':
                    cx = float(tokens[i])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'h':
                    cx += float(tokens[i])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'V':
                    cy = float(tokens[i])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'v':
                    cy += float(tokens[i])
                    commands.append(('line', (tp(cx, cy),)))
                    i += 1
                    lc_x = lc_y = None
                elif cmd == 'C':
                    x1, y1 = float(tokens[i]), float(tokens[i+1])
                    x2, y2 = float(tokens[i+2]), float(tokens[i+3])
                    cx, cy = float(tokens[i+4]), float(tokens[i+5])
                    commands.append(('curve', (tp(x1, y1), tp(x2, y2), tp(cx, cy))))
                    i += 6
                    lc_x, lc_y = x2, y2
                elif cmd == 'c':
                    bx, by = cx, cy
                    x1, y1 = bx + float(tokens[i]), by + float(tokens[i+1])
                    x2, y2 = bx + float(tokens[i+2]), by + float(tokens[i+3])
                    cx, cy = bx + float(tokens[i+4]), by + float(tokens[i+5])
                    commands.append(('curve', (tp(x1, y1), tp(x2, y2), tp(cx, cy))))
                    i += 6
                    lc_x, lc_y = x2, y2
                elif cmd in 'Ss':
                    bx, by = (0.0, 0.0) if cmd == 'S' else (cx, cy)
                    rx1 = 2 * cx - lc_x if lc_x is not None else cx
                    ry1 = 2 * cy - lc_y if lc_y is not None else cy
                    x2 = bx + float(tokens[i])
                    y2 = by + float(tokens[i+1])
                    cx = bx + float(tokens[i+2])
                    cy = by + float(tokens[i+3])
                    commands.append(('curve', (tp(rx1, ry1), tp(x2, y2), tp(cx, cy))))
                    i += 4
                    lc_x, lc_y = x2, y2
                elif cmd in 'Qq':
                    bx, by = (0.0, 0.0) if cmd == 'Q' else (cx, cy)
                    qx1 = bx + float(tokens[i])
                    qy1 = by + float(tokens[i+1])
                    ex = bx + float(tokens[i+2])
                    ey = by + float(tokens[i+3])
                    cx1 = cx + 2 / 3 * (qx1 - cx)
                    cy1 = cy + 2 / 3 * (qy1 - cy)
                    cx2 = ex + 2 / 3 * (qx1 - ex)
                    cy2 = ey + 2 / 3 * (qy1 - ey)
                    cx, cy = ex, ey
                    commands.append(('curve', (tp(cx1, cy1), tp(cx2, cy2), tp(cx, cy))))
                    i += 4
                    lc_x, lc_y = qx1, qy1
                elif cmd in 'Tt':
                    qx1 = 2 * cx - lc_x if lc_x is not None else cx
                    qy1 = 2 * cy - lc_y if lc_y is not None else cy
                    bx, by = (0.0, 0.0) if cmd == 'T' else (cx, cy)
                    ex = bx + float(tokens[i])
                    ey = by + float(tokens[i+1])
                    cx1 = cx + 2 / 3 * (qx1 - cx)
                    cy1 = cy + 2 / 3 * (qy1 - cy)
                    cx2 = ex + 2 / 3 * (qx1 - ex)
                    cy2 = ey + 2 / 3 * (qy1 - ey)
                    cx, cy = ex, ey
                    commands.append(('curve', (tp(cx1, cy1), tp(cx2, cy2), tp(cx, cy))))
                    i += 2
                    lc_x, lc_y = qx1, qy1
                elif cmd in 'Aa' and i + 6 < len(tokens):
                    bx, by = cx, cy
                    rx_a, ry_a = abs(float(tokens[i])), abs(float(tokens[i+1]))
                    phi_a = float(tokens[i+2])
                    la, sw = int(float(tokens[i+3])), int(float(tokens[i+4]))
                    if cmd == 'A':
                        cx, cy = float(tokens[i+5]), float(tokens[i+6])
                    else:
                        cx, cy = bx + float(tokens[i+5]), by + float(tokens[i+6])
                    for bz in _arc_to_bezier(bx, by, rx_a, ry_a, phi_a, la, sw, cx, cy):
                        commands.append((
                            'curve',
                            (tp(bz[0], bz[1]), tp(bz[2], bz[3]), tp(bz[4], bz[5])),
                        ))
                    lc_x = lc_y = None
                    i += 7
                else:
                    i += 1
            except (IndexError, ValueError):
                i += 1
    return commands


def commands_bbox(commands):
    """Return (x, y, w, h) for a parsed path command list."""
    xs = []
    ys = []
    for _, points in commands:
        for x, y in points:
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    bx = min(xs)
    by = min(ys)
    bw = max(xs) - bx or 1
    bh = max(ys) - by or 1
    return bx, by, bw, bh


def commands_to_stencil_path(commands, ox, oy, w, h):
    """Serialize parsed path commands into draw.io stencil XML path nodes."""
    def nx(x):
        return (x - ox) / w * 100 if w else 0

    def ny(y):
        return (y - oy) / h * 100 if h else 0

    parts = []
    for kind, points in commands:
        if kind == 'move':
            x, y = points[0]
            parts.append(f'<move x="{nx(x):.2f}" y="{ny(y):.2f}"/>')
        elif kind == 'line':
            x, y = points[0]
            parts.append(f'<line x="{nx(x):.2f}" y="{ny(y):.2f}"/>')
        elif kind == 'curve':
            (x1, y1), (x2, y2), (x3, y3) = points
            parts.append(
                f'<curve x1="{nx(x1):.2f}" y1="{ny(y1):.2f}"'
                f' x2="{nx(x2):.2f}" y2="{ny(y2):.2f}"'
                f' x3="{nx(x3):.2f}" y3="{ny(y3):.2f}"/>'
            )
        elif kind == 'close':
            parts.append('<close/>')
    return ''.join(parts)


def path_to_stencil(d, ox, oy, w, h):
    """Convert SVG path d attribute to draw.io stencil XML in 0-100 coordinate space."""
    return commands_to_stencil_path(path_commands(d), ox, oy, w, h)


def _compress_drawio_text(text):
    """
    Encode inline draw.io payloads the same way diagrams.net Graph.compress does:
    URI-encode text, raw-deflate it, then base64 it.
    """
    data = quote(text, safe=_URI_SAFE).encode('utf-8')
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(data) + compressor.flush()
    return b64encode(compressed).decode('ascii')


def make_stencil_style_from_xml(xml, fill, stroke, sw, op):
    """Build a draw.io stencil style string from stencil XML."""
    if not xml:
        return None
    encoded = _compress_drawio_text(xml)
    return (
        f'shape=stencil({encoded});fillColor={fill};strokeColor={stroke};'
        f'strokeWidth={sw};opacity={op};'
    )


def make_stencil_style_from_commands(commands, ox, oy, w, h, fill, stroke, sw, op, fill_rule='nonzero'):
    """Build a draw.io stencil style string from transformed path commands."""
    sp = commands_to_stencil_path(commands, ox, oy, w, h)
    if not sp:
        return None
    # Path coordinates are normalized to 0..100, so the stencil view box must
    # use the same 100x100 logical space to avoid an extra size scale in draw.io.
    if fill_rule == 'evenodd':
        path_elem = f'<path fillrule="evenodd">{sp}</path>'
    else:
        path_elem = f'<path>{sp}</path>'
    xml = ('<shape w="100" h="100" aspect="variable" strokewidth="inherit">'
           f'<background>{path_elem}<fillstroke/></background></shape>')
    return make_stencil_style_from_xml(xml, fill, stroke, sw, op)


def make_stencil_style(d, ox, oy, w, h, fill, stroke, sw, op, fill_rule='nonzero'):
    """Build a draw.io stencil style string from an SVG path."""
    return make_stencil_style_from_commands(path_commands(d), ox, oy, w, h, fill, stroke, sw, op, fill_rule)
