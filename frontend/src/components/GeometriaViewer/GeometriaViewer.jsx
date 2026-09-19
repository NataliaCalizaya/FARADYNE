import React, { useState, useEffect, useRef } from 'react';
import { Stage, Layer, Line, Circle, Rect, Text, Group } from 'react-konva';
import { AlertTriangle, CheckCircle, Save, Plus, Loader2, HelpCircle, ZoomIn, ZoomOut, RefreshCw } from 'lucide-react';
import { planosApi } from '../../api/planos';

export const GeometriaViewer = ({ idPlano, idModelo2D, onGeometriaConfirmed, onNext }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  
  // Real geometry loaded from API or local edits (stored in original drawing coordinates)
  const [poligonos, setPoligonos] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [capas, setCapas] = useState([]);
  const [cotasAltura, setCotasAltura] = useState([]);
  const [boundingBox, setBoundingBox] = useState(null);
  const [isValidated, setIsValidated] = useState(false);

  // Pan & Zoom state
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isDraggingPan = useRef(false);
  const lastPointerPos = useRef({ x: 0, y: 0 });

  // New polygon creation state
  const [isAddingSurface, setIsAddingSurface] = useState(false);
  const [currentNewPoints, setCurrentNewPoints] = useState([]);

  // Selected item state
  const [selectedPolyIndex, setSelectedPolyIndex] = useState(null);
  const [selectedLineIndex, setSelectedLineIndex] = useState(null);

  const containerRef = useRef(null);
  const [stageDimensions, setStageDimensions] = useState({ width: 620, height: 420 });

  useEffect(() => {
    if (idPlano) {
      loadPreview(idPlano);
    }
  }, [idPlano]);

  const loadPreview = async (planoId) => {
    setLoading(true);
    setError(null);
    try {
      const data = await planosApi.getPlanoPreview(planoId);
      if (data) {
        setPoligonos(data.poligonos || []);
        setLineas(data.lineas || []);
        setCapas(data.capas || []);
        setCotasAltura(data.cotas_altura || []);
        setBoundingBox(data.bounding_box || null);
        setIsValidated(!!data.validado);
      }
    } catch (err) {
      console.error('Error al cargar la vista previa:', err);
      setError('No se pudo obtener la geometría del plano.');
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // COORDINATE TRANSFORMATIONS (Original Drawing Coords <-> Konva Screen Coords)
  // ============================================================================
  const getTransform = () => {
    const margin = 30;
    const cw = stageDimensions.width - margin * 2;
    const ch = stageDimensions.height - margin * 2;

    if (!boundingBox || boundingBox.min_x === undefined) {
      return { scale: 1 * zoom, offsetX: margin + pan.x, offsetY: margin + pan.y };
    }

    const bboxWidth = (boundingBox.max_x - boundingBox.min_x) || 1;
    const bboxHeight = (boundingBox.max_y - boundingBox.min_y) || 1;

    const baseScaleX = cw / bboxWidth;
    const baseScaleY = ch / bboxHeight;
    const baseScale = Math.min(baseScaleX, baseScaleY);

    const scale = baseScale * zoom;
    const offsetX = margin + (cw - bboxWidth * scale) / 2 - boundingBox.min_x * scale + pan.x;
    const offsetY = margin + (ch - bboxHeight * scale) / 2 - boundingBox.min_y * scale + pan.y;

    return { scale, offsetX, offsetY };
  };

  const transformPoint = (x, y) => {
    const { scale, offsetX, offsetY } = getTransform();
    return [x * scale + offsetX, y * scale + offsetY];
  };

  const inverseTransformPoint = (screenX, screenY) => {
    const { scale, offsetX, offsetY } = getTransform();
    return [(screenX - offsetX) / scale, (screenY - offsetY) / scale];
  };

  // Zoom wheel handler
  const handleWheel = (e) => {
    e.evt.preventDefault();
    const zoomFactor = e.evt.deltaY < 0 ? 1.12 : 0.89;
    setZoom((z) => Math.max(0.3, Math.min(6.0, z * zoomFactor)));
  };

  // Pan pointer handlers
  const handlePointerDown = (e) => {
    if (isAddingSurface) return;
    if (e.target === e.target.getStage()) {
      isDraggingPan.current = true;
      lastPointerPos.current = { x: e.evt.clientX, y: e.evt.clientY };
    }
  };

  const handlePointerMove = (e) => {
    if (!isDraggingPan.current) return;
    const dx = e.evt.clientX - lastPointerPos.current.x;
    const dy = e.evt.clientY - lastPointerPos.current.y;
    lastPointerPos.current = { x: e.evt.clientX, y: e.evt.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  };

  const handlePointerUp = () => {
    isDraggingPan.current = false;
  };

  // Keyboard shortcut to finalize polygon when drawing (Enter key)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (isAddingSurface && e.key === 'Enter') {
        finalizeNewPolygon();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isAddingSurface, currentNewPoints]);

  const handleStageClick = (e) => {
    if (!isAddingSurface) return;
    const stage = e.target.getStage();
    const point = stage.getPointerPosition();
    if (point) {
      setCurrentNewPoints((prev) => [...prev, [point.x, point.y]]);
    }
  };

  const handleStageDblClick = () => {
    if (isAddingSurface) {
      finalizeNewPolygon();
    }
  };

  const finalizeNewPolygon = () => {
    if (currentNewPoints.length >= 3) {
      const originalPoints = currentNewPoints.map(([sx, sy]) => inverseTransformPoint(sx, sy));
      const newPoly = {
        id: `user_poly_${Date.now()}`,
        footprint: originalPoints,
        puntos: originalPoints,
        capa: 'CAPA_USUARIO',
        color: '#2a9d5c',
        cerrado: true,
      };
      setPoligonos((prev) => [...prev, newPoly]);
    }
    setCurrentNewPoints([]);
    setIsAddingSurface(false);
  };

  // Dragging vertex handlers
  const handleVertexDrag = (polyIndex, vertexIndex, newScreenX, newScreenY) => {
    const [origX, origY] = inverseTransformPoint(newScreenX, newScreenY);
    setPoligonos((prev) => {
      const copy = JSON.parse(JSON.stringify(prev));
      const targetPoly = copy[polyIndex];
      const ptsKey = targetPoly.footprint ? 'footprint' : 'puntos';
      if (targetPoly[ptsKey]) {
        targetPoly[ptsKey][vertexIndex] = [origX, origY];
      }
      if (targetPoly.puntos && ptsKey !== 'puntos') {
        targetPoly.puntos[vertexIndex] = [origX, origY];
      }
      return copy;
    });
  };

  const handleLineVertexDrag = (lineIndex, vertexPos, newScreenX, newScreenY) => {
    const [origX, origY] = inverseTransformPoint(newScreenX, newScreenY);
    setLineas((prev) => {
      const copy = JSON.parse(JSON.stringify(prev));
      if (vertexPos === 'inicio') {
        copy[lineIndex].inicio = [origX, origY];
        if (copy[lineIndex].start) copy[lineIndex].start = [origX, origY];
      } else {
        copy[lineIndex].fin = [origX, origY];
        if (copy[lineIndex].end) copy[lineIndex].end = [origX, origY];
      }
      return copy;
    });
  };

  // Save edits API call
  const handleSaveCorrections = async (validadoFlag = false) => {
    const targetId = idModelo2D || idPlano;
    if (!targetId) return;

    setSaving(true);
    setError(null);
    try {
      await planosApi.updateModelo2D(targetId, {
        poligonos,
        lineas,
        capas,
        validado: validadoFlag,
      });

      setIsValidated(validadoFlag);
      if (validadoFlag && onGeometriaConfirmed) {
        onGeometriaConfirmed({ validado: true });
      }
    } catch (err) {
      console.error('Error guardando modelo 2D:', err);
      setError(err.response?.data?.detail || 'Error al guardar las modificaciones.');
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmGeometry = () => {
    handleSaveCorrections(true);
  };

  const resetView = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  const isEmptyGeometry = !loading && poligonos.length === 0 && lineas.length === 0;

  return (
    <div className="space-y-4">
      {/* Alert Header */}
      <div className="p-3 bg-amber-50 border border-amber-200 text-amber-900 rounded-md flex items-start gap-2 text-xs">
        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <strong className="font-semibold">CORRECTOR 2D INTERACTIVO:</strong> Arrastre vértices o use "Agregar superficie". Rueda para Zoom, arrastre el fondo para desplazarse. Selección activa en magenta (<span className="text-[#d946ef] font-bold">#d946ef</span>).
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-xs">
          {error}
        </div>
      )}

      {/* Editing Toolbar */}
      <div className="bg-white border border-gray-200 rounded-md p-3 shadow-sm flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsAddingSurface(!isAddingSurface)}
            className={`px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 transition ${
              isAddingSurface
                ? 'bg-brand-blue text-white border-brand-blue'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Plus className="w-3.5 h-3.5" /> {isAddingSurface ? 'Haga clic en el lienzo (Enter o Doble clic para finalizar)' : 'Agregar Superficie'}
          </button>

          <div className="h-4 w-[1px] bg-gray-300 mx-1" />

          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(6.0, z * 1.2))}
            className="p-1.5 bg-white border border-gray-300 hover:bg-gray-50 rounded text-gray-700 transition"
            title="Acercar (Zoom In)"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
            className="p-1.5 bg-white border border-gray-300 hover:bg-gray-50 rounded text-gray-700 transition"
            title="Alejar (Zoom Out)"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={resetView}
            className="p-1.5 bg-white border border-gray-300 hover:bg-gray-50 rounded text-gray-700 transition"
            title="Restablecer encuadre"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleSaveCorrections(false)}
            disabled={saving}
            className="px-3 py-1.5 bg-white text-gray-700 border border-gray-300 hover:bg-gray-50 rounded text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5 text-gray-600" /> {saving ? 'Guardando...' : 'Guardar Correcciones'}
          </button>
        </div>
      </div>

      {/* Konva Stage Canvas Container */}
      <div
        ref={containerRef}
        className="relative bg-slate-50 border border-gray-300 rounded-md h-[460px] flex items-center justify-center overflow-hidden cursor-grab active:cursor-grabbing"
      >
        {loading ? (
          <div className="flex flex-col items-center justify-center text-gray-500">
            <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-2" />
            <span className="text-xs font-medium">Cargando elementos geométricos del plano...</span>
          </div>
        ) : isEmptyGeometry ? (
          <div className="flex flex-col items-center justify-center p-6 text-center text-amber-800 bg-amber-50/50 rounded-lg max-w-md border border-amber-200">
            <HelpCircle className="w-10 h-10 text-amber-500 mb-2" />
            <h4 className="font-semibold text-sm">No se reconoció geometría en este archivo</h4>
            <p className="text-xs text-gray-600 mt-1">
              El parser vectorial no detectó polígonos o líneas cerradas automáticamente. Use el botón <strong>"Agregar Superficie"</strong> en la barra superior para dibujarla manualmente.
            </p>
          </div>
        ) : (
          <Stage
            width={stageDimensions.width}
            height={stageDimensions.height}
            onWheel={handleWheel}
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={handlePointerUp}
            onClick={handleStageClick}
            onDblClick={handleStageDblClick}
          >
            <Layer>
              {/* Raw Lines rendering with non-scaling stroke effect */}
              {lineas.map((line, lineIdx) => {
                const p1 = line.inicio || line.start || [0, 0];
                const p2 = line.fin || line.end || [0, 0];
                const [sp1x, sp1y] = transformPoint(p1[0], p1[1]);
                const [sp2x, sp2y] = transformPoint(p2[0], p2[1]);
                const isSelected = selectedLineIndex === lineIdx;
                const strokeColor = isSelected ? '#d946ef' : (line.color || '#94a3b8');
                const strokeWidth = (isSelected ? 2.5 : 1.0) / zoom;

                return (
                  <Group key={`line-${lineIdx}`}>
                    <Line
                      points={[sp1x, sp1y, sp2x, sp2y]}
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedLineIndex(lineIdx);
                        setSelectedPolyIndex(null);
                      }}
                    />
                    <Circle
                      x={sp1x}
                      y={sp1y}
                      radius={4 / zoom}
                      fill={strokeColor}
                      draggable
                      onDragMove={(e) => handleLineVertexDrag(lineIdx, 'inicio', e.target.x(), e.target.y())}
                    />
                    <Circle
                      x={sp2x}
                      y={sp2y}
                      radius={4 / zoom}
                      fill={strokeColor}
                      draggable
                      onDragMove={(e) => handleLineVertexDrag(lineIdx, 'fin', e.target.x(), e.target.y())}
                    />
                  </Group>
                );
              })}

              {/* Roof Regions / Polygons rendering */}
              {poligonos.map((poly, polyIdx) => {
                const pts = poly.footprint || poly.puntos || [];
                const screenPoints = pts.flatMap(([x, y]) => transformPoint(x, y));
                const isSelected = selectedPolyIndex === polyIdx;
                const strokeColor = isSelected ? '#d946ef' : (poly.color || '#1a6dba');
                const fillColor = isSelected ? '#d946ef33' : strokeColor + '22';
                const strokeWidth = (isSelected ? 3.0 : 2.0) / zoom;

                return (
                  <Group key={`poly-${polyIdx}`}>
                    <Line
                      points={screenPoints}
                      closed={poly.cerrado !== false}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      onClick={(e) => {
                        e.cancelBubble = true;
                        setSelectedPolyIndex(polyIdx);
                        setSelectedLineIndex(null);
                      }}
                    />

                    {/* Draggable Vertices */}
                    {pts.map((pt, vIdx) => {
                      const [sx, sy] = transformPoint(pt[0], pt[1]);
                      return (
                        <Circle
                          key={`poly-${polyIdx}-v-${vIdx}`}
                          x={sx}
                          y={sy}
                          radius={5 / zoom}
                          fill={strokeColor}
                          stroke="#ffffff"
                          strokeWidth={1.5 / zoom}
                          draggable
                          onDragMove={(e) => {
                            handleVertexDrag(polyIdx, vIdx, e.target.x(), e.target.y());
                          }}
                        />
                      );
                    })}
                  </Group>
                );
              })}

              {/* Active in-progress surface points */}
              {currentNewPoints.length > 0 && (
                <Group>
                  <Line
                    points={currentNewPoints.flat()}
                    stroke="#2a9d5c"
                    strokeWidth={2 / zoom}
                    dash={[4 / zoom, 4 / zoom]}
                  />
                  {currentNewPoints.map((pt, idx) => (
                    <Circle key={`new-pt-${idx}`} x={pt[0]} y={pt[1]} radius={5 / zoom} fill="#2a9d5c" />
                  ))}
                </Group>
              )}

              {/* Elevation / Level Badges */}
              {cotasAltura.map((cota, idx) => {
                const pos = cota.posicion || [50, 50];
                const [spx, spy] = transformPoint(pos[0], pos[1]);
                return (
                  <Group key={`cota-${idx}`} x={spx} y={spy}>
                    <Rect width={60} height={18} fill="#1a6dba" cornerRadius={2} />
                    <Text
                      text={cota.texto || `+${cota.valor}m`}
                      fontSize={9}
                      fontStyle="bold"
                      fill="#ffffff"
                      x={5}
                      y={4}
                    />
                  </Group>
                );
              })}
            </Layer>
          </Stage>
        )}
      </div>

      {/* Confirmation Actions */}
      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={handleConfirmGeometry}
          disabled={saving}
          className="px-5 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
        >
          <CheckCircle className="w-4 h-4" /> {isValidated ? 'Geometría Confirmada ✓' : 'Confirmar Geometría'}
        </button>
        {isValidated && (
          <button
            type="button"
            onClick={onNext}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded text-xs transition"
          >
            Siguiente paso (Modelo 3D) →
          </button>
        )}
      </div>
    </div>
  );
};

export default GeometriaViewer;
