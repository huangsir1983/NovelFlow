'use client';

import { useState, useEffect, type RefObject } from 'react';

/**
 * Magnetic "+" button hook — shared by all canvas node types.
 *
 * Tracks mouse position via window mousemove (not onMouseEnter/Leave)
 * so the button remains reachable even when the mouse crosses the gap
 * between the card edge and the button rest position.
 *
 * Behavior:
 *  - Mouse over card area (with right-side padding): show button at rest position
 *  - Mouse within SNAP_RADIUS of button: "snap" — button follows cursor
 *  - Mouse elsewhere: hide button
 *  - When menu is open: always show button
 */

const BTN_SIZE = 32;
const SNAP_RADIUS = 50;

export function useMagneticButton(
  cardRef: RefObject<HTMLDivElement | null>,
  cardWidth: number,
  disabled?: boolean,
) {
  const [btnState, setBtnState] = useState<'hidden' | 'visible' | 'snapped'>('hidden');
  const [btnPos, setBtnPos] = useState({ x: 0, y: 0 });
  const [menuOpen, setMenuOpen] = useState(false);

  const restOffsetX = cardWidth + 50;

  useEffect(() => {
    if (disabled) return;
    // Keep button visible while menu is open
    if (menuOpen) {
      setBtnState('visible');
      return;
    }

    const onMove = (e: MouseEvent) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const zoom = rect.width / cardWidth || 1;
      const mx = (e.clientX - rect.left) / zoom;
      const my = (e.clientY - rect.top) / zoom;
      const localH = rect.height / zoom;
      const restY = localH / 2;

      const dist = Math.sqrt((mx - restOffsetX) ** 2 + (my - restY) ** 2);

      if (dist < SNAP_RADIUS) {
        setBtnState('snapped');
        setBtnPos({ x: mx, y: my });
      } else {
        // Extended hit area: card bounds + 90px to the right for the button zone
        const overArea = mx >= -10 && mx <= cardWidth + 90 && my >= -20 && my <= localH + 20;
        if (overArea) {
          setBtnState('visible');
          setBtnPos({ x: restOffsetX, y: restY });
        } else {
          setBtnState('hidden');
        }
      }
    };

    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, [cardRef, cardWidth, disabled, menuOpen, restOffsetX]);

  const showBtn = btnState !== 'hidden' || menuOpen;
  const isSnapped = btnState === 'snapped';

  return { showBtn, btnPos, isSnapped, menuOpen, setMenuOpen, BTN_SIZE };
}
