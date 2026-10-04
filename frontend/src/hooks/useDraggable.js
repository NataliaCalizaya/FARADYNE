import { useCallback, useRef, useState } from 'react';

/**
 * Hace arrastrable un panel flotante (position: absolute) dentro de su contenedor.
 *
 * Uso:
 *   const drag = useDraggable();
 *   <aside ref={drag.ref} style={drag.style}>
 *     <div {...drag.handleProps}>agarrar acá</div>
 *   </aside>
 *
 * Doble clic sobre la manija → vuelve a su posición original.
 */
export function useDraggable() {
    const ref = useRef(null);
    const [offset, setOffset] = useState({ x: 0, y: 0 });

    const onPointerDown = useCallback((event) => {
        if (event.button !== 0 || !ref.current) return;
        event.preventDefault();
        event.stopPropagation();

        const el = ref.current;
        const parent = el.offsetParent || document.body;
        const elRect = el.getBoundingClientRect();
        const parentRect = parent.getBoundingClientRect();
        const start = { x: event.clientX, y: event.clientY };
        const base = offset;

        // Límites para que el panel no se salga del contenedor
        const minDx = parentRect.left - elRect.left;
        const maxDx = parentRect.right - elRect.right;
        const minDy = parentRect.top - elRect.top;
        const maxDy = parentRect.bottom - elRect.bottom;
        const clamp = (v, min, max) => Math.min(Math.max(v, min), max);

        const handleMove = (ev) => {
            const dx = clamp(ev.clientX - start.x, minDx, maxDx);
            const dy = clamp(ev.clientY - start.y, minDy, maxDy);
            setOffset({ x: base.x + dx, y: base.y + dy });
        };
        const handleUp = () => {
            window.removeEventListener('pointermove', handleMove);
            window.removeEventListener('pointerup', handleUp);
        };
        window.addEventListener('pointermove', handleMove);
        window.addEventListener('pointerup', handleUp);
    }, [offset]);

    const reset = useCallback(() => setOffset({ x: 0, y: 0 }), []);

    return {
        ref,
        style: { transform: `translate(${offset.x}px, ${offset.y}px)` },
        handleProps: {
            onPointerDown,
            onDoubleClick: reset,
            title: 'Arrastrá para mover · doble clic para volver a su lugar',
            style: { cursor: 'move', touchAction: 'none' },
        },
        reset,
    };
}

export default useDraggable;