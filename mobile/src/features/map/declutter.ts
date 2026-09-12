export interface ScreenPoint {
  left: number;
  top: number;
}

export interface ScreenSize {
  width: number;
  height: number;
}

export interface PositionedItem<T> extends ScreenPoint {
  item: T;
}

export function selectDecluttered<T>(
  items: T[],
  project: (item: T) => ScreenPoint,
  viewport: ScreenSize,
  cellSize: number,
  maximumItems: number,
): PositionedItem<T>[] {
  const occupied = new Set<string>();
  const selected: PositionedItem<T>[] = [];
  for (const item of items) {
    const point = project(item);
    if (
      point.left < 0 ||
      point.top < 0 ||
      point.left > viewport.width ||
      point.top > viewport.height
    ) {
      continue;
    }
    const cell = `${Math.floor(point.left / cellSize)}:${Math.floor(point.top / cellSize)}`;
    if (occupied.has(cell)) {
      continue;
    }
    occupied.add(cell);
    selected.push({ item, ...point });
    if (selected.length >= maximumItems) {
      break;
    }
  }
  return selected;
}
