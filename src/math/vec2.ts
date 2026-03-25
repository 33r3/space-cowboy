export interface Vec2 {
  x: number
  y: number
}

export const Vec2 = {
  create(x: number, y: number): Vec2 { return { x, y } },
  zero(): Vec2 { return { x: 0, y: 0 } },
  clone(v: Vec2): Vec2 { return { x: v.x, y: v.y } },

  add(a: Vec2, b: Vec2): Vec2 { return { x: a.x + b.x, y: a.y + b.y } },
  sub(a: Vec2, b: Vec2): Vec2 { return { x: a.x - b.x, y: a.y - b.y } },
  scale(v: Vec2, s: number): Vec2 { return { x: v.x * s, y: v.y * s } },

  dot(a: Vec2, b: Vec2): number { return a.x * b.x + a.y * b.y },
  lengthSq(v: Vec2): number { return v.x * v.x + v.y * v.y },
  length(v: Vec2): number { return Math.sqrt(Vec2.lengthSq(v)) },
  distSq(a: Vec2, b: Vec2): number { return Vec2.lengthSq(Vec2.sub(a, b)) },
  dist(a: Vec2, b: Vec2): number { return Math.sqrt(Vec2.distSq(a, b)) },

  normalize(v: Vec2): Vec2 {
    const len = Vec2.length(v)
    if (len === 0) return Vec2.zero()
    return Vec2.scale(v, 1 / len)
  },

  lerp(a: Vec2, b: Vec2, t: number): Vec2 {
    return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
  },
}
