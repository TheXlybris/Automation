"""
ImageAnimator — Efeitos atmosféricos sobre imagens estáticas.

Engine de composição de camadas alpha-blended para gerar vídeos
a partir de imagens fixas com efeitos como ken_burns, fireflies,
fog, god_rays, particles, snow, rain, ripple, pulse_light.

Stack: PIL + NumPy + MoviePy (CPU-only, ~5s por 10s de vídeo).
"""

from __future__ import annotations

import math
import os
import random
import tempfile
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

# ─── Registry ────────────────────────────────────────

EFFECT_REGISTRY: Dict[str, type] = {}


def register(cls: type) -> type:
    """Decorator para registar subclasses de EffectLayer."""
    if not hasattr(cls, "name") or cls.name == "abstract":
        raise ValueError("Efeito registado deve ter um 'name' definido.")
    EFFECT_REGISTRY[cls.name] = cls
    return cls


# ─── Base Class ────────────────────────────────────────

class EffectLayer:
    """Classe base para todas as camadas de efeito."""

    name: str = "abstract"

    def __init__(self, params: dict):
        self.params = params

    def render(
        self,
        frame_idx: int,
        total_frames: int,
        base_img: Image.Image,
    ) -> Image.Image:
        """
        Retorna um PIL.Image.RGBA com o efeito aplicado para o frame dado.
        Deve ser sobreposto à imagem base via alpha_composite.
        """
        raise NotImplementedError

    @classmethod
    def default_params(cls) -> dict:
        """Parâmetros por omissão para UI/presets."""
        return {}


# ─── Helpers ───────────────────────────────────────────

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


# ─── Core Effects — Task 4: fog + god_rays ──────────────────

def _make_fog_band(w: int, h: int, density: float = 0.5, opacity: int = 80) -> Image.Image:
    """Gera uma banda horizontal de névoa com variação suave."""
    # Usar gradiente horizontal + ruído simples
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    # Gradiente de alpha da esq-para-dir com sine wave
    for x in range(w):
        alpha = int(opacity * (0.5 + 0.5 * math.sin(x / (w * 0.15))))
        alpha = int(alpha * density)
        arr[:, x, 3] = alpha
    arr[:, :, 0:3] = 220  # cinza claro
    return Image.fromarray(arr, "RGBA")


@register
class FogLayer(EffectLayer):
    """Névoa a deslizar horizontalmente."""

    name = "fog"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "density": 0.5,
            "speed": 1.0,          # px por frame (relativo ao tamanho)
            "opacity": 80,
            "y_offset": 0.0,       # posição vertical da névoa (0.0=topo, 1.0=fundo)
            "height": 0.3,         # altura relativa da banda (0.0-1.0)
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        p = self.params
        density = p.get("density", 0.5)
        speed = p.get("speed", 1.0)
        opacity = p.get("opacity", 80)
        y_offset = p.get("y_offset", 0.0)
        band_rel_h = p.get("height", 0.3)

        band_h = max(20, int(h * band_rel_h))
        fog_img = _make_fog_band(w, band_h, density, opacity)

        # Deslocamento horizontal baseado no frame
        shift = int(frame_idx * speed * (w / 240)) % w
        shifted = Image.new("RGBA", (w, band_h), (0, 0, 0, 0))
        shifted.paste(fog_img.crop((w - shift, 0, w, band_h)), (0, 0))
        shifted.paste(fog_img.crop((0, 0, w - shift, band_h)), (shift, 0))

        y = int(y_offset * (h - band_h))
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        canvas.paste(shifted, (0, y), shifted)
        return canvas


@register
class GodRaysLayer(EffectLayer):
    """Raios de luz volumétricos a oscilar — blend aditivo sobre a imagem base."""

    name = "god_rays"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "angle": 45.0,
            "intensity": 0.6,
            "speed": 0.8,
            "color": "#FFF8E7",
            "ray_count": 7,
            "center_x": 0.5,
            "center_y": 0.0,
            "spread": 35.0,      # abertura total em graus
            "length": 1.2,       # multiplicador do comprimento
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        p = self.params
        angle_base = math.radians(p.get("angle", 45.0))
        intensity = p.get("intensity", 0.6)
        speed = p.get("speed", 0.8)
        color_hex = p.get("color", "#FFF8E7")
        ray_count = p.get("ray_count", 7)
        cx = p.get("center_x", 0.5) * w
        cy = p.get("center_y", 0.0) * h
        spread = math.radians(p.get("spread", 35.0))
        length_mult = p.get("length", 1.2)

        # Oscilação mais pronunciada: ±25% do spread
        t = frame_idx / max(total_frames - 1, 1)
        phase = t * speed * 2 * math.pi
        wobble = math.sin(phase) * spread * 0.25
        angle = angle_base + wobble

        rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        # Criar máscara de luz via numpy — VETORIZADO
        base_arr = np.array(base_img.convert("RGBA")).astype(np.float32) / 255.0
        light = np.zeros((h, w, 3), dtype=np.float32)
        max_len = max(w, h) * length_mult

        # Coordenadas meshgrid (uma vez)
        yy, xx = np.mgrid[0:h, 0:w]
        xx = xx.astype(np.float32)
        yy = yy.astype(np.float32)

        # Raios divergentes
        for i in range(ray_count):
            frac = i / max(ray_count - 1, 1)
            ray_angle = angle - spread / 2 + spread * frac
            ray_angle += math.sin(phase * 1.3 + i * 2.1) * spread * 0.08
            length = max_len * (0.7 + 0.3 * math.sin(phase + i))
            x1 = cx + math.cos(ray_angle) * length
            y1 = cy + math.sin(ray_angle) * length
            thickness = 8 + 12 * (1 - frac)
            self._draw_wedge_fast(light, xx, yy, cx, cy, x1, y1, thickness, rgb, intensity)

        # Suavizar a luz
        light_img = Image.fromarray(
            (np.clip(light, 0, 1) * 255).astype(np.uint8), "RGB"
        )
        light_img = light_img.filter(ImageFilter.GaussianBlur(radius=6))
        light = np.array(light_img).astype(np.float32) / 255.0

        # Blend aditivo
        result = np.clip(base_arr[:, :, :3] + light, 0, 1)

        out = np.zeros((h, w, 4), dtype=np.uint8)
        out[:, :, :3] = (result * 255).astype(np.uint8)
        out[:, :, 3] = 255
        return Image.fromarray(out, "RGBA")

    def _draw_wedge_fast(self, light: np.ndarray, xx: np.ndarray, yy: np.ndarray,
                         x0: float, y0: float, x1: float, y1: float,
                         thickness: float, rgb: Tuple[int, int, int], intensity: float):
        """Vetorizado: calcula distância perpendicular de TODOS os pixeis à linha do raio."""
        dx = x1 - x0
        dy = y1 - y0
        line_len = math.sqrt(dx*dx + dy*dy)
        if line_len == 0:
            return

        # Distância perpendicular (vetorizado)
        dist = np.abs(dy * xx - dx * yy + x1 * y0 - y1 * x0) / line_len

        # Projeção ao longo da linha (0=origem, 1=ponta)
        t_proj = ((xx - x0) * dx + (yy - y0) * dy) / (line_len * line_len)
        t_proj = np.clip(t_proj, 0, 1)

        # Falloff axial: mais brilhante na origem
        axial = 1.0 - t_proj * 0.5
        # Falloff radial gaussiano
        radial = np.exp(-(dist * dist) / (thickness * thickness * 0.5))
        # Máscara combinada
        mask = axial * radial * intensity

        # Adicionar luz (vetorizado)
        light[:, :, 0] += (rgb[0] / 255.0) * mask
        light[:, :, 1] += (rgb[1] / 255.0) * mask
        light[:, :, 2] += (rgb[2] / 255.0) * mask


# ─── Core Effects — Task 2: ken_burns + pulse_light (mantidos abaixo) ──────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size")

    def __init__(self, w: int, h: int, speed: float, size_range: Tuple[float, float]):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        angle = random.uniform(0, 2 * math.pi)
        spd = random.uniform(speed * 0.5, speed * 1.5)
        self.vx = math.cos(angle) * spd
        self.vy = math.sin(angle) * spd
        self.max_life = random.uniform(60, 180)
        self.life = random.uniform(0, self.max_life)
        self.size = random.uniform(size_range[0], size_range[1])

    def update(self, w: int, h: int, dt: float = 1.0):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        # Wrap-around
        if self.x < 0:
            self.x += w
        elif self.x > w:
            self.x -= w
        if self.y < 0:
            self.y += h
        elif self.y > h:
            self.y -= h

    def alive(self) -> bool:
        return self.life > 0

    def reset(self, w: int, h: int, speed: float, size_range: Tuple[float, float]):
        edge = random.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            self.x, self.y = random.uniform(0, w), -5
        elif edge == "bottom":
            self.x, self.y = random.uniform(0, w), h + 5
        elif edge == "left":
            self.x, self.y = -5, random.uniform(0, h)
        else:
            self.x, self.y = w + 5, random.uniform(0, h)
        angle = random.uniform(0, 2 * math.pi)
        spd = random.uniform(speed * 0.5, speed * 1.5)
        self.vx = math.cos(angle) * spd
        self.vy = math.sin(angle) * spd
        self.max_life = random.uniform(60, 180)
        self.life = self.max_life
        self.size = random.uniform(size_range[0], size_range[1])


class ParticleSystem:
    """Base para sistemas de partículas 2D (random walk, wrap-around, respawn)."""

    def __init__(
        self,
        count: int,
        bounds: Tuple[int, int],
        speed: float = 2.0,
        size_range: Tuple[float, float] = (2.0, 6.0),
    ):
        self.w, self.h = bounds
        self.speed = speed
        self.size_range = size_range
        self.particles: List[Particle] = [
            Particle(self.w, self.h, speed, size_range) for _ in range(count)
        ]

    def update(self, dt: float = 1.0):
        for p in self.particles:
            p.update(self.w, self.h, dt)
            if not p.alive():
                p.reset(self.w, self.h, self.speed, self.size_range)

    def draw_on(self, draw: ImageDraw.ImageDraw, color: Tuple[int, int, int, int]):
        for p in self.particles:
            alpha = int(color[3] * (p.life / p.max_life)) if p.max_life > 0 else color[3]
            r = p.size * 0.5
            draw.ellipse(
                [p.x - r, p.y - r, p.x + r, p.y + r],
                fill=(color[0], color[1], color[2], alpha),
            )


def _make_glow(size: float, color: Tuple[int, int, int], intensity: float) -> Image.Image:
    """Gera um radial gradient para glow de partícula."""
    s = int(size * 4)
    if s < 4:
        s = 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cx, cy = s // 2, s // 2
    for y in range(s):
        for x in range(s):
            dx, dy = x - cx, y - cy
            dist = math.sqrt(dx * dx + dy * dy) / (s * 0.5)
            if dist >= 1.0:
                continue
            a = int((1.0 - dist ** 2) * 255 * intensity)
            img.putpixel((x, y), (color[0], color[1], color[2], a))
    return img


# Cache simples de glows (evita recriar o mesmo gradiente)
_GLOW_CACHE: Dict[Tuple[float, Tuple[int, int, int], float], Image.Image] = {}


def _cached_glow(size: float, color: Tuple[int, int, int], intensity: float) -> Image.Image:
    key = (round(size, 1), color, round(intensity, 2))
    if key not in _GLOW_CACHE:
        _GLOW_CACHE[key] = _make_glow(size, color, intensity)
    return _GLOW_CACHE[key]


@register
class FirefliesLayer(EffectLayer):
    """Partículas amarelas/cianas a flutuar com glow radial."""

    name = "fireflies"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "count": 30,
            "speed": 1.5,
            "size": [3.0, 8.0],
            "color": ["#FFD700", "#00FFFF"],
            "glow": 0.6,
        }

    def __init__(self, params: dict):
        super().__init__(params)
        p = self.params
        self.system = ParticleSystem(
            count=p.get("count", 30),
            bounds=(1920, 1080),  # será ajustado no primeiro render
            speed=p.get("speed", 1.5),
            size_range=tuple(p.get("size", [3.0, 8.0])),
        )
        self.colors_hex = p.get("color", ["#FFD700", "#00FFFF"])
        self.glow_intensity = p.get("glow", 0.6)
        self._palette: List[Tuple[int, int, int]] = [
            tuple(int(self.colors_hex[i].lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
            if isinstance(self.colors_hex, list) and len(self.colors_hex) > i
            else (255, 215, 0)
            for i in range(2)
        ]

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        # Ajusta bounds se mudou de tamanho
        if self.system.w != w or self.system.h != h:
            self.system.w, self.system.h = w, h

        self.system.update(dt=1.0)

        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        for p in self.system.particles:
            color_idx = int(p.life % 2)  # alterna entre as duas cores
            rgb = self._palette[color_idx]
            glow = _cached_glow(p.size, rgb, self.glow_intensity)
            gx, gy = int(p.x - glow.width // 2), int(p.y - glow.height // 2)
            canvas.paste(glow, (gx, gy), glow)

        return canvas


@register
class ParticlesLayer(EffectLayer):
    """Pó / polen branco semi-transparente a flutuar verticalmente."""

    name = "particles"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "count": 50,
            "speed": 0.8,
            "size": [1.0, 3.5],
            "drift": 0.5,
        }

    def __init__(self, params: dict):
        super().__init__(params)
        p = self.params
        self.drift = p.get("drift", 0.5)
        self.system = ParticleSystem(
            count=p.get("count", 50),
            bounds=(1920, 1080),
            speed=p.get("speed", 0.8),
            size_range=tuple(p.get("size", [1.0, 3.5])),
        )
        # Override vy para movimento predominantemente vertical
        for part in self.system.particles:
            part.vy = abs(part.vy)  # sempre para baixo / flutuar
            part.vx *= self.drift

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        if self.system.w != w or self.system.h != h:
            self.system.w, self.system.h = w, h

        self.system.update(dt=1.0)

        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for p in self.system.particles:
            alpha = int(180 * (p.life / p.max_life)) if p.max_life > 0 else 180
            r = p.size * 0.5
            draw.ellipse(
                [p.x - r, p.y - r, p.x + r, p.y + r],
                fill=(255, 255, 255, alpha),
            )
        return canvas

@register
class KenBurnsLayer(EffectLayer):
    """Pan + zoom suave sobre a imagem base (crop centralizado + resize)."""

    name = "ken_burns"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "pan_x": [0.0, 0.0],       # (start, end) — percentagem da largura
            "pan_y": [0.0, 0.0],       # (start, end) — percentagem da altura
            "zoom_start": 1.0,         # escala no início (1.0 = 100%)
            "zoom_end": 1.05,          # escala no fim
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        t = frame_idx / max(total_frames - 1, 1)
        t = _ease_in_out(t)

        p = self.params
        pan_x_start, pan_x_end = p.get("pan_x", [0.0, 0.0])
        pan_y_start, pan_y_end = p.get("pan_y", [0.0, 0.0])
        zoom_start = p.get("zoom_start", 1.0)
        zoom_end = p.get("zoom_end", 1.05)

        zoom = _lerp(zoom_start, zoom_end, t)
        pan_x = _lerp(pan_x_start, pan_x_end, t)
        pan_y = _lerp(pan_y_start, pan_y_end, t)

        # Tamanho da janela de crop inversamente proporcional ao zoom
        crop_w = int(w / zoom)
        crop_h = int(h / zoom)

        # Offset em pixels baseado no pan
        offset_x = int((w - crop_w) * 0.5 + pan_x * w)
        offset_y = int((h - crop_h) * 0.5 + pan_y * h)

        # Clamp
        offset_x = max(0, min(offset_x, w - crop_w))
        offset_y = max(0, min(offset_y, h - crop_h))

        cropped = base_img.crop((offset_x, offset_y, offset_x + crop_w, offset_y + crop_h))
        return cropped.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA")


@register
class PulseLightLayer(EffectLayer):
    """Pulsação sinusoidal de brilho global."""

    name = "pulse_light"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "min_brightness": 0.85,
            "max_brightness": 1.15,
            "speed": 1.0,              # ciclos completos durante a duração total
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        p = self.params
        min_b = p.get("min_brightness", 0.85)
        max_b = p.get("max_brightness", 1.15)
        speed = p.get("speed", 1.0)

        t = frame_idx / max(total_frames - 1, 1)
        phase = t * speed * 2 * math.pi
        factor = _lerp(min_b, max_b, (math.sin(phase) + 1) / 2)

        enhancer = ImageEnhance.Brightness(base_img)
        return enhancer.enhance(factor).convert("RGBA")


@register
class LightningLayer(EffectLayer):
    """Relâmpagos — flashes súbitos e aleatórios de brilho extremo."""

    name = "lightning"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "frequency": 1.0,        # strikes por segundo (aprox)
            "intensity": 1.8,        # pico de brilho
            "flash_duration": 2,     # frames de duração do flash
            "color": "#E8F4FF",     # cor do flash
            "decay": 0.3,            # velocidade de queda após o pico
        }

    def __init__(self, params: dict):
        super().__init__(params)
        self._strikes: list = []
        self._rng = random.Random(42)  # seed fixo → reprodutível

    def _compute_strikes(self, total_frames: int):
        if self._strikes:
            return
        freq = self.params.get("frequency", 1.0)
        fps = 24  # assumido para cálculo de intervalo
        avg_interval = int(fps / max(freq, 0.01))
        t = self._rng.randint(0, avg_interval)  # primeiro strike aleatório
        while t < total_frames:
            # intervalo aleatório: gauss centrado na média
            interval = int(self._rng.gauss(avg_interval, avg_interval * 0.4))
            interval = max(3, interval)
            t += interval
            if t < total_frames:
                self._strikes.append(t)

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        self._compute_strikes(total_frames)
        p = self.params
        intensity = p.get("intensity", 1.8)
        flash_dur = p.get("flash_duration", 2)
        decay = p.get("decay", 0.3)

        brightness = 1.0
        for strike in self._strikes:
            if frame_idx >= strike and frame_idx < strike + flash_dur:
                brightness = intensity
                break
            elif frame_idx >= strike + flash_dur:
                frames_since = frame_idx - (strike + flash_dur)
                # Decaimento exponencial a partir do pico
                val = 1.0 + (intensity - 1.0) * (decay ** frames_since)
                if val > brightness:
                    brightness = val

        brightness = min(brightness, intensity)
        enhancer = ImageEnhance.Brightness(base_img)
        return enhancer.enhance(brightness).convert("RGBA")


@register
class LightningBoltLayer(EffectLayer):
    """Raio / Relâmpago visível — midpoint displacement com ramificações naturais."""

    name = "lightning_bolt"
    blend_mode = "additive"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "frequency": 0.5,        # strikes por segundo
            "segments": 8,           # iterações midpoint displacement (4-12)
            "displacement": 0.15,    # desvio máximo relativo à altura (0.05-0.50)
            "glow": 0.7,             # intensidade do halo eléctrico
            "color": "#FFFFFF",      # cor do núcleo do raio
            "core_width": 3,         # grossura do núcleo
            "flash_duration": 3,     # frames visíveis
            "fork_chance": 0.35,     # probabilidade de ramificação (0.0-1.0)
        }

    def __init__(self, params: dict):
        super().__init__(params)
        self._strikes: list = []
        self._bolt_cache: dict = {}   # (w,h,strike_idx) -> (trunk_points, forks[])
        self._rng = random.Random(99)

    def _compute_strikes(self, total_frames: int):
        if self._strikes:
            return
        freq = self.params.get("frequency", 0.5)
        fps = 24
        avg_interval = int(fps / max(freq, 0.01))
        t = self._rng.randint(0, avg_interval)
        while t < total_frames:
            interval = int(self._rng.gauss(avg_interval, avg_interval * 0.4))
            interval = max(3, interval)
            t += interval
            if t < total_frames:
                self._strikes.append(t)

    def _midpoint_displacement(self, x0, y0, x1, y1, segments, max_disp):
        """Gera path fractal com midpoint displacement. Retorna lista de pontos."""
        points = [(x0, y0), (x1, y1)]
        total_len = math.hypot(x1 - x0, y1 - y0)
        if total_len < 1:
            return points

        for _ in range(segments):
            new_points = [points[0]]
            for i in range(len(points) - 1):
                x_a, y_a = points[i]
                x_b, y_b = points[i + 1]
                mx = (x_a + x_b) / 2.0
                my = (y_a + y_b) / 2.0
                dx = x_b - x_a
                dy = y_b - y_a
                seg_len = math.hypot(dx, dy)
                if seg_len < 0.5:
                    new_points.append((x_b, y_b))
                    continue
                # Deslocamento perpendicular — sigma proporcional ao comprimento do segmento
                perp_x = -dy / seg_len
                perp_y = dx / seg_len
                sigma = max_disp * (seg_len / total_len)
                offset = self._rng.gauss(0, sigma)
                mx += perp_x * offset
                my += perp_y * offset
                new_points.append((mx, my))
                new_points.append((x_b, y_b))
            points = new_points
        return points

    def _generate_fork(self, trunk_points, max_disp):
        """Cria uma ramificação a partir de um ponto do tronco."""
        n = len(trunk_points)
        if n < 4:
            return None
        # Escolher ponto no meio (não topo nem fundo)
        idx = self._rng.randint(n // 3, n * 2 // 3)
        fx, fy = trunk_points[idx]
        # Direção aleatória, preferencialmente para baixo e lateral
        angle = self._rng.uniform(0.3, 2.5)
        trunk_len = math.hypot(trunk_points[-1][0] - trunk_points[0][0],
                               trunk_points[-1][1] - trunk_points[0][1])
        fork_len = trunk_len * self._rng.uniform(0.2, 0.5)
        end_x = fx + math.cos(angle) * fork_len
        end_y = fy + math.sin(angle) * fork_len
        fork_segments = max(3, self.params.get("segments", 8) - 3)
        fork_disp = max_disp * 0.5
        return self._midpoint_displacement(fx, fy, end_x, end_y, fork_segments, fork_disp)

    def _render_bolt(self, w, h, trunk_points, fork_list, color, core_width, glow):
        """Desenha raio em camadas: glow (blur) por baixo, core (nítido) por cima."""
        # --- Glow layer (blur permitido) ---
        glow_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_img)
        glow_w = int(glow * 10 + core_width)
        glow_alpha = int(min(255, glow * 160))
        glow_color = (*color, glow_alpha)

        for i in range(len(trunk_points) - 1):
            gdraw.line([trunk_points[i], trunk_points[i + 1]], fill=glow_color, width=glow_w)
        for fork_pts in fork_list or []:
            for i in range(len(fork_pts) - 1):
                gdraw.line([fork_pts[i], fork_pts[i + 1]], fill=glow_color, width=max(1, glow_w // 2))

        if glow > 0:
            radius = int(glow * 5 + 1)
            glow_img = glow_img.filter(ImageFilter.GaussianBlur(radius=radius))

        # --- Core layer (SEM blur — mantém nítido) ---
        core_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(core_img)
        core_color = (*color, 255)

        for i in range(len(trunk_points) - 1):
            cdraw.line([trunk_points[i], trunk_points[i + 1]], fill=core_color, width=core_width)
        for fork_pts in fork_list or []:
            for i in range(len(fork_pts) - 1):
                cdraw.line([fork_pts[i], fork_pts[i + 1]], fill=core_color, width=max(1, core_width - 1))

        # --- Composite: glow por baixo, core por cima ---
        return Image.alpha_composite(glow_img, core_img)

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        self._compute_strikes(total_frames)
        p = self.params
        segments = p.get("segments", 8)
        disp_ratio = p.get("displacement", 0.15)
        max_disp = h * max(0.05, min(0.5, disp_ratio))
        glow = p.get("glow", 0.7)
        color_hex = p.get("color", "#FFFFFF")
        core_width = p.get("core_width", 3)
        flash_dur = p.get("flash_duration", 3)
        fork_chance = p.get("fork_chance", 0.35)

        rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

        # Ver se há strike activo
        active = None
        for strike in self._strikes:
            if frame_idx >= strike and frame_idx < strike + flash_dur:
                key = (w, h, strike)
                if key not in self._bolt_cache:
                    start_x = self._rng.uniform(w * 0.2, w * 0.8)
                    end_x = self._rng.uniform(w * 0.2, w * 0.8)
                    trunk = self._midpoint_displacement(start_x, 0, end_x, h, segments, max_disp)

                    forks = []
                    if self._rng.random() < fork_chance:
                        fork = self._generate_fork(trunk, max_disp)
                        if fork:
                            forks.append(fork)
                    if self._rng.random() < fork_chance * 0.6:
                        fork = self._generate_fork(trunk, max_disp)
                        if fork:
                            forks.append(fork)

                    self._bolt_cache[key] = (trunk, forks)
                active = self._bolt_cache[key]
                break

        if not active:
            return Image.new("RGBA", (w, h), (0, 0, 0, 0))

        trunk, forks = active
        return self._render_bolt(w, h, trunk, forks, rgb, core_width, glow)


# ─── Public API — Task 5: compositor + MoviePy export ──────────────────
class RainLayer(EffectLayer):
    """Chuva — gotas verticais com trail e splash."""

    name = "rain"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "count": 100,
            "speed": 20.0,           # velocidade de queda (px/frame) — máx 30
            "length": 15.0,          # comprimento médio da gota
            "angle": 0.0,            # inclinação (0=vertical, >0=vento direita)
            "intensity": 0.6,        # opacidade das gotas
            "color": "#A0B8D0",     # cor azulada
        }

    def __init__(self, params: dict):
        super().__init__(params)
        self._drops: list = []
        self._rng = random.Random(7)

    def _init_drops(self, w: int, h: int):
        if self._drops:
            return
        p = self.params
        count = p.get("count", 100)
        speed = p.get("speed", 12.0)
        length = p.get("length", 15.0)
        angle = math.radians(p.get("angle", 0.0))
        for _ in range(count):
            self._drops.append({
                "x": self._rng.uniform(0, w),
                "y": self._rng.uniform(-h, h),
                "speed": self._rng.uniform(speed * 0.7, speed * 1.3),
                "length": self._rng.uniform(length * 0.5, length * 1.5),
                "width": self._rng.uniform(0.5, 1.5),
            })

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        self._init_drops(w, h)
        p = self.params
        speed = p.get("speed", 12.0)
        angle = math.radians(p.get("angle", 0.0))
        intensity = p.get("intensity", 0.6)
        color_hex = p.get("color", "#A0B8D0")
        rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        alpha = int(255 * intensity)

        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        for drop in self._drops:
            drop["y"] += drop["speed"] * math.cos(angle)
            drop["x"] += drop["speed"] * math.sin(angle)
            if drop["y"] > h + 20:
                drop["y"] = self._rng.uniform(-30, -5)
                drop["x"] = self._rng.uniform(0, w)

            x1 = drop["x"] - drop["length"] * sin_a
            y1 = drop["y"] - drop["length"] * cos_a
            draw.line(
                [(x1, y1), (drop["x"], drop["y"])],
                fill=(*rgb, alpha),
                width=max(1, int(drop["width"])),
            )
        return canvas


@register
class SnowLayer(EffectLayer):
    """Neve — flocos a flutuarem para baixo com oscilação lateral."""

    name = "snow"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "count": 80,
            "speed": 2.5,
            "size": [2.0, 6.0],
            "sway": 1.0,             # amplitude da oscilação lateral
            "opacity": 0.8,
        }

    def __init__(self, params: dict):
        super().__init__(params)
        self._flakes: list = []
        self._rng = random.Random(13)

    def _init_flakes(self, w: int, h: int):
        if self._flakes:
            return
        p = self.params
        count = p.get("count", 80)
        speed = p.get("speed", 2.5)
        size_range = tuple(p.get("size", [2.0, 6.0]))
        for i in range(count):
            self._flakes.append({
                "x": self._rng.uniform(0, w),
                "y": self._rng.uniform(-h, h),
                "speed": self._rng.uniform(speed * 0.5, speed * 1.5),
                "size": self._rng.uniform(size_range[0], size_range[1]),
                "phase": self._rng.uniform(0, 2 * math.pi),
                "freq": self._rng.uniform(0.02, 0.08),
            })

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        self._init_flakes(w, h)
        p = self.params
        sway = p.get("sway", 1.0)
        opacity = p.get("opacity", 0.8)
        alpha = int(255 * opacity)

        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        for flake in self._flakes:
            flake["y"] += flake["speed"]
            flake["x"] += math.sin(frame_idx * flake["freq"] + flake["phase"]) * sway
            if flake["y"] > h + 10:
                flake["y"] = self._rng.uniform(-20, -5)
                flake["x"] = self._rng.uniform(0, w)
            if flake["x"] < -10:
                flake["x"] = w + 10
            elif flake["x"] > w + 10:
                flake["x"] = -10

            r = flake["size"] * 0.5
            draw.ellipse(
                [flake["x"] - r, flake["y"] - r, flake["x"] + r, flake["y"] + r],
                fill=(255, 255, 255, alpha),
            )
        return canvas


@register
class RippleLayer(EffectLayer):
    """Ondulação / Ripple — deforma a imagem com ondas circulares."""

    name = "ripple"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "center_x": 0.5,
            "center_y": 0.5,
            "count": 3,              # número de ondas simultâneas
            "speed": 1.0,            # expansão das ondas
            "amplitude": 8.0,        # intensidade da deformação (px)
            "frequency": 0.05,       # frequência espacial das ondas
            "decay": 0.3,            # atenuação com a distância
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        p = self.params
        cx = int(p.get("center_x", 0.5) * w)
        cy = int(p.get("center_y", 0.5) * h)
        count = p.get("count", 3)
        speed = p.get("speed", 1.0)
        amp = p.get("amplitude", 8.0)
        freq = p.get("frequency", 0.05)
        decay = p.get("decay", 0.3)

        # Vetorizado com numpy
        arr = np.array(base_img).astype(np.float32)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

        dx = xx - cx
        dy = yy - cy
        dist = np.sqrt(dx**2 + dy**2)

        displacement = np.zeros_like(dist)
        for i in range(count):
            phase = (frame_idx * speed * 0.3 + i * (2 * math.pi / count)) % (2 * math.pi)
            wave = np.sin(dist * freq + phase) * amp * np.exp(-dist * decay / max(w, h))
            displacement += wave

        # Clamp displacement
        new_xx = np.clip(xx + displacement, 0, w - 1)
        new_yy = np.clip(yy + displacement, 0, h - 1)

        # Map pixels — bilinear aproximado com arredondamento
        ix = np.floor(new_xx).astype(np.int32)
        iy = np.floor(new_yy).astype(np.int32)
        ix = np.clip(ix, 0, w - 2)
        iy = np.clip(iy, 0, h - 2)
        fx = new_xx - ix
        fy = new_yy - iy

        # Bilinear interpolation
        c00 = arr[iy, ix]
        c10 = arr[iy, ix + 1]
        c01 = arr[iy + 1, ix]
        c11 = arr[iy + 1, ix + 1]

        out = (
            c00 * (1 - fx[:, :, None]) * (1 - fy[:, :, None]) +
            c10 * fx[:, :, None] * (1 - fy[:, :, None]) +
            c01 * (1 - fx[:, :, None]) * fy[:, :, None] +
            c11 * fx[:, :, None] * fy[:, :, None]
        )

        return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


# ─── Effect: Cascading Water (mask-aware) ──────────────────

@register
class CascadeWaterLayer(EffectLayer):
    """
    Efeito de cascata de agua — scroll vertical + streaks + espuma (topo e base).
    Aplica-se APENAS na zona definida pela mascara (branco = agua, preto = intacto).
    """

    name = "cascading_water"

    @classmethod
    def default_params(cls) -> dict:
        return {
            "mask_path": "",           # path PNG (branco = zona de agua)
            "fall_speed": 2.0,         # px/frame scroll vertical
            "foam_intensity": 0.7,     # 0..1 quantidade espuma
            "streak_density": 30,      # numero de streaks
            "blur_amount": 3.0,        # motion blur vertical
            "turbulence": 0.3,         # aleatoriedade no fluxo
            "water_color": "#4a7fb5",  # tinte azulado da agua
        }

    def render(self, frame_idx: int, total_frames: int, base_img: Image.Image) -> Image.Image:
        w, h = base_img.size
        p = self.params
        fall_speed = p.get("fall_speed", 2.0)
        foam_int = p.get("foam_intensity", 0.7)
        streak_density = p.get("streak_density", 30)
        blur_amt = p.get("blur_amount", 3.0)
        water_color = p.get("water_color", "#4a7fb5")
        mask_path = p.get("mask_path", "")

        # Carregar mascara
        if mask_path and os.path.exists(mask_path):
            mask = Image.open(mask_path).convert("L").resize((w, h), Image.Resampling.BILINEAR)
            mask_arr = np.array(mask).astype(np.float32) / 255.0
        else:
            mask_arr = np.ones((h, w), dtype=np.float32)

        mask_inv = 1.0 - mask_arr

        base_arr = np.array(base_img.convert("RGBA")).astype(np.float32) / 255.0
        result = base_arr[:, :, :3].copy()

        # Bounding box da mascara para otimizar
        ys, xs = np.where(mask_arr > 0.05)
        if len(xs) == 0:
            return base_img.convert("RGBA")
        my1, my2 = ys.min(), ys.max() + 1
        mx1, mx2 = xs.min(), xs.max() + 1

        zone_h = my2 - my1
        zone_w = mx2 - mx1
        if zone_h < 10 or zone_w < 10:
            return base_img.convert("RGBA")

        zone_mask = mask_arr[my1:my2, mx1:mx2]
        zone_base = result[my1:my2, mx1:mx2].copy()

        # --- Scroll vertical da imagem original (loop) ---
        shift = int(frame_idx * fall_speed) % zone_h
        scrolled = np.roll(zone_base, shift=shift, axis=0)

        # --- Motion blur vertical na zona da agua ---
        if blur_amt > 0:
            blurred = np.zeros_like(scrolled)
            kernel = int(blur_amt * 2 + 1)
            half = kernel // 2
            for dy in range(-half, half + 1):
                weight = 1.0 - abs(dy) / (half + 0.5)
                rolled = np.roll(scrolled, dy, axis=0)
                blurred += rolled * weight
            blurred /= (blurred.sum(axis=2, keepdims=True).max() + 0.001)
            blurred = np.clip(blurred, 0, 1)
            zone_result = scrolled * 0.5 + blurred * 0.5
        else:
            zone_result = scrolled

        # --- Streaks verticais (linhas de agua em movimento) ---
        if streak_density > 0:
            rng = np.random.RandomState(42 + frame_idx % 100)  # seeded para consistencia
            for i in range(streak_density):
                sx = rng.randint(0, zone_w)
                sw = rng.randint(1, 4)
                speed = rng.uniform(1.0, 4.0) * fall_speed
                brightness = rng.uniform(0.6, 0.95)
                sy = int((frame_idx * speed + rng.randint(0, zone_h)) % zone_h)
                for dw in range(sw):
                    x = min(sx + dw, zone_w - 1)
                    y_start = max(0, sy - 6)
                    y_end = min(zone_h, sy + 7)
                    for dy in range(y_start, y_end):
                        zone_result[dy, x] *= brightness

        # --- Espuma no topo (onde a mascara comeca) ---
        if foam_int > 0:
            rng = np.random.RandomState(43 + frame_idx % 100)
            foam_zone = int(zone_h * 0.15)
            for y in range(foam_zone):
                foam_alpha = (1.0 - y / max(foam_zone, 1)) * foam_int
                noise = rng.random(zone_w) * 0.3
                zone_result[y, :, :] += noise[:, None] * foam_alpha
            # Espuma na base (onde a agua "bate")
            foam_zone_bot = int(zone_h * 0.12)
            for y in range(zone_h - foam_zone_bot, zone_h):
                dy = y - (zone_h - foam_zone_bot)
                foam_alpha = (dy / max(foam_zone_bot, 1)) * foam_int * 0.8
                noise = rng.random(zone_w) * 0.25
                zone_result[y, :, :] += noise[:, None] * foam_alpha

        # --- Tint azulado da agua ---
        wc = tuple(int(water_color.lstrip("#")[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        tint_strength = 0.12
        zone_result = zone_result * (1 - tint_strength) + np.array(wc) * tint_strength

        # Composite: zona animada com alpha da mascara, resto intacto
        zone_result = np.clip(
            zone_result * np.stack([zone_mask]*3, axis=2) +
            zone_base * np.stack([1-zone_mask]*3, axis=2),
            0, 1
        )
        result[my1:my2, mx1:mx2] = zone_result

        out = np.zeros((h, w, 4), dtype=np.uint8)
        out[:, :, :3] = (np.clip(result, 0, 1) * 255).astype(np.uint8)
        out[:, :, 3] = 255
        return Image.fromarray(out, "RGBA")


# ─── Public API — Task 5: compositor + MoviePy export ──────────────────

def animate_image(
    img_path: str,
    effects_config: List[dict],
    duration: float = 10.0,
    fps: int = 24,
    size: Tuple[int, int] | None = None,
) -> str:
    """
    Gera um vídeo MP4 a partir de uma imagem estática + lista de efeitos.
    """
    from moviepy import ImageSequenceClip  # lazy import para evitar startup lenta

    base = Image.open(img_path).convert("RGBA")
    if size:
        base = base.resize(size, Image.Resampling.LANCZOS)
    w, h = base.size

    total_frames = int(duration * fps)
    layers = []
    for cfg in effects_config:
        name = cfg.get("name")
        params = cfg.get("params", {})
        if name not in EFFECT_REGISTRY:
            raise ValueError(f"Efeito desconhecido: {name!r}. Disponíveis: {list(EFFECT_REGISTRY.keys())}")
        layers.append(EFFECT_REGISTRY[name](params))

    frames_np: List[np.ndarray] = []
    for i in range(total_frames):
        canvas = base.copy()
        for layer in layers:
            overlay = layer.render(i, total_frames, base)
            # Assegura tamanho igual
            if overlay.size != (w, h):
                overlay = overlay.resize((w, h), Image.Resampling.LANCZOS)
            # Se overlay é quase totalmente opaco, substitui canvas (efeito já inclui base)
            # Se tem transparência, faz alpha composite
            if overlay.mode == "RGBA":
                arr = np.array(overlay)
                mean_alpha = arr[:, :, 3].mean()
                if mean_alpha > 250:
                    canvas = overlay  # efeito já fez blend interno
                else:
                    canvas = Image.alpha_composite(canvas, overlay)
            else:
                canvas = overlay.convert("RGBA")
        frames_np.append(np.array(canvas.convert("RGB")))

    clip = ImageSequenceClip(frames_np, fps=fps)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(tmp_fd)
    clip.write_videofile(
        tmp_path,
        fps=fps,
        codec="libx264",
        audio=False,
        logger=None,
    )
    clip.close()
    # Libertar memória dos arrays grandes
    del frames_np
    return tmp_path


def list_effects() -> List[dict]:
    """Lista os efeitos registados com os seus parâmetros por omissão."""
    return [
        {
            "name": cls.name,
            "params": cls.default_params(),
        }
        for cls in EFFECT_REGISTRY.values()
    ]


# ─── Sanity check ao import ────────────────────────────
if __name__ == "__main__":
    print(f"ImageAnimator loaded — {len(EFFECT_REGISTRY)} effect(s) registered.")
    print("Registry keys:", list(EFFECT_REGISTRY.keys()))
