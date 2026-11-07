// Imports geometry from multi-part 3MF packages exported by Bambu Studio,
// OrcaSlicer and PrusaSlicer (3MF Production Extension: p:path).
// This intentionally imports geometry and placement, not printer presets / G-code.
import * as THREE from 'three';
import { unzipSync, strFromU8 } from 'three/addons/libs/fflate.module.js';

const MAX_EXPANDED_BYTES = 80 * 1024 * 1024;
const MAX_TRIANGLES = 500000;
const MAX_OBJECTS = 100;
const hexColor = value => {
  const text = String(value || '').trim();
  return /^#[0-9a-f]{6}(?:[0-9a-f]{2})?$/i.test(text)
    ? Number.parseInt(text.slice(1, 7), 16) : null;
};
// Bambu face-paint labels are stored as a compact, reversed nibble tree.
// Whole-triangle labels are exact; subdivided triangles use the most
// frequent explicitly painted state for a preview (not slicer-level accuracy).
function paintedExtruder(encoded) {
  if (!encoded || !/^[0-9a-f]+$/i.test(encoded) || encoded.length > 4096) return null;
  const digits = Array.from(encoded, c => Number.parseInt(c, 16)).reverse();
  let pos = 0, nodes = 0;
  const counts = new Map();
  const walk = (depth, weight) => {
    if (++nodes > 4096 || depth > 48 || pos >= digits.length) throw Error('Peinture 3MF invalide');
    const code = digits[pos++], split = code & 3, upper = code >> 2;
    if (split) {
      for (let i = 0; i < split + 1; i++) walk(depth + 1, weight / (split + 1));
    } else {
      let state = upper;
      if (upper === 3) {
        let extension = 0, next;
        do {
          if (pos >= digits.length) throw Error('Peinture 3MF incomplète');
          next = digits[pos++];
          if (next === 15) extension++;
        } while (next === 15 && extension < 32);
        state = 3 + extension * 15 + next;
      }
      if (state > 0 && state <= 32) counts.set(state, (counts.get(state) || 0) + weight);
    }
  };
  try {
    walk(0, 1);
    let selected = null, maximum = 0;
    for (const [slot, count] of counts) if (count > maximum) {selected = slot; maximum = count;}
    return selected;
  } catch (_) {return null;}
}
const children = (node, name) =>
  Array.from(node?.children || []).filter(element => element.localName === name);
const first = (node, name) => children(node, name)[0];
const localPath = element =>
  Array.from(element?.attributes || []).find(attribute => attribute.localName === 'path')?.value || '';
const getUnitScale = unit => ({
  micron: .001, millimeter: 1, centimeter: 10, meter: 1000,
  inch: 25.4, foot: 304.8
})[unit || 'millimeter'] || 1;

function normalized(path) {
  const segments = [];
  for (const part of String(path || '').replaceAll('\\', '/').split('/')) {
    if (!part || part === '.') continue;
    if (part === '..') segments.pop();
    else segments.push(part);
  }
  return segments.join('/');
}

function transform(value) {
  const matrix = new THREE.Matrix4();
  if (!value) return matrix;
  const v = String(value).trim().split(/\s+/).map(Number);
  if (v.length !== 12 || !v.every(Number.isFinite))
    throw Error('Matrice de positionnement 3MF invalide.');
  // 3MF stores a 3x4 affine transform: columns are contiguous,
  // with translation in entries 9, 10, 11.
  return matrix.set(
    v[0], v[3], v[6], v[9],
    v[1], v[4], v[7], v[10],
    v[2], v[5], v[8], v[11],
    0, 0, 0, 1
  );
}

function parseXml(bytes, path) {
  const xml = new DOMParser().parseFromString(strFromU8(bytes), 'application/xml');
  if (xml.getElementsByTagName('parsererror').length || xml.documentElement?.localName !== 'model')
    throw Error('Modèle XML 3MF invalide : ' + path);
  return xml;
}

export function parse3MFProduction(arrayBuffer, fallbackName = 'Objet 3MF') {
  // Isolate caches per file: a rejected 3MF must not affect the next import.
  const xmlCache = new Map();
  // Include Bambu filament and per-part settings alongside the model XML.
  // Limit the total expanded data before decompression.
  let declaredSize = 0;
  const zip = unzipSync(new Uint8Array(arrayBuffer), {
    filter: entry => {
      if (!/\.model$|(?:^|\/)(?:model_settings|project_settings)\.config$/i.test(entry.name)) return false;
      declaredSize += entry.originalSize || 0;
      if (declaredSize > MAX_EXPANDED_BYTES)
        throw Error('Projet 3MF trop volumineux une fois décompressé.');
      return true;
    }
  });
  const archive = new Map();
  for (const [name, bytes] of Object.entries(zip)) {
    const key = normalized(name);
    archive.set(key.toLowerCase(), { path: key, bytes });
  }
  if (![...archive.keys()].some(path => /\.model$/i.test(path)))
    throw Error('Aucun modèle 3D trouvé dans le fichier 3MF.');
  let filamentColors = [];
  const project = archive.get('metadata/project_settings.config');
  if (project) {
    try {
      const cfg = JSON.parse(strFromU8(project.bytes));
      const array = cfg.filament_colour || cfg.filament_color || [];
      if (Array.isArray(array)) filamentColors = array.slice(0, 32).map(hexColor);
    } catch (err) {console.warn('Palette de filaments 3MF non lisible', err);}
  }
  const objectSlots = new Map(), partSlots = new Map();
  const settings = archive.get('metadata/model_settings.config');
  if (settings) {
    try {
      const xml = new DOMParser().parseFromString(strFromU8(settings.bytes), 'application/xml');
      if (xml.getElementsByTagName('parsererror').length) throw Error('XML invalide');
      const getSlot = node => {
        const m = children(node, 'metadata').find(n => n.getAttribute('key') === 'extruder');
        const slot = Number(m?.getAttribute('value'));
        return Number.isInteger(slot) && slot >= 1 && slot <= 32 ? slot : null;
      };
      for (const object of Array.from(xml.getElementsByTagName('object'))) {
        const id = object.getAttribute('id');
        const slot = getSlot(object);
        if (id && slot) objectSlots.set(id, slot);
        for (const part of children(object, 'part')) {
          const partId = part.getAttribute('id');
          const partSlot = getSlot(part);
          if (partId && partSlot) partSlots.set(partId, partSlot);
        }
      }
    } catch (err) {console.warn('Affectations des filaments 3MF non lisibles', err);}
  }
  const load = path => {
    const entry = archive.get(normalized(path).toLowerCase());
    if (!entry) throw Error('Modèle référencé absent : ' + path);
    const cacheKey = entry.path.toLowerCase();
    if (!xmlCache.has(cacheKey)) xmlCache.set(cacheKey, parseXml(entry.bytes, entry.path));
    return { path: entry.path, xml: xmlCache.get(cacheKey) };
  };
  const byName = Array.from(archive.values()).filter(entry => /\.model$/i.test(entry.path));
  const rootFile = byName.find(entry => /(^|\/)3dmodel\.model$/i.test(entry.path)) || byName[0];
  const root = load(rootFile.path);
  const unitScale = getUnitScale(root.xml.documentElement.getAttribute('unit'));
  const unitMatrix = new THREE.Matrix4().makeScale(unitScale, unitScale, unitScale);
  const geometries = [];
  const active = new Set();
  let triangleCount = 0;

  function findObject(file, id) {
    const resources = first(file.xml.documentElement, 'resources');
    const object = children(resources, 'object').find(item => item.getAttribute('id') === String(id));
    if (!object) throw Error('Objet 3MF introuvable : ' + id + ' dans ' + file.path);
    return object;
  }

  function resolvePart(current, path) {
    if (!path) return current;
    const requested = normalized(path);
    if (archive.has(requested.toLowerCase())) return load(requested);
    const dir = current.path.split('/').slice(0, -1).join('/');
    return load(normalized(dir + '/' + path));
  }

  function colorGroups(file) {
    const resources = first(file.xml.documentElement, 'resources');
    const palette = new Map();
    for (const group of children(resources, 'colorgroup')) {
      const id = group.getAttribute('id');
      palette.set(id, children(group, 'color').map(c => hexColor(c.getAttribute('color'))));
    }
    for (const group of children(resources, 'basematerials')) {
      const id = group.getAttribute('id');
      palette.set(id, children(group, 'base').map(c => hexColor(c.getAttribute('displaycolor'))));
    }
    return palette;
  }
  function appendMesh(mesh, worldMatrix, name, defaultColor, file, object, slot) {
    const groups = colorGroups(file);
    const objectPid = object.getAttribute('pid');
    const objectPindex = Number(object.getAttribute('pindex') || '0');
    const objectColors = groups.get(objectPid) || [];
    const objectColor = objectColors[objectPindex];
    const vertices = children(first(mesh, 'vertices'), 'vertex');
    const triangles = children(first(mesh, 'triangles'), 'triangle');
    if (!vertices.length || !triangles.length) return;
    triangleCount += triangles.length;
    if (triangleCount > MAX_TRIANGLES) throw Error('Modèle 3MF trop complexe pour l’Atelier.');
    if (geometries.length >= MAX_OBJECTS) throw Error('Le projet contient trop de pièces.');
    const points = vertices.map(v => {
      const p = ['x','y','z'].map(axis => Number(v.getAttribute(axis)));
      if (!p.every(Number.isFinite)) throw Error('Coordonnée de sommet 3MF invalide.');
      return p;
    });
    const coords = new Float32Array(triangles.length * 9);
    const triangleColors = new Array(triangles.length);
    let index = 0, faceIndex = 0;
    for (const triangle of triangles) {
      let faceColor = null;
      const pid = triangle.getAttribute('pid') || objectPid;
      const palette = groups.get(pid);
      const p1 = triangle.getAttribute('p1');
      const pindex = p1 !== null ? Number(p1) : objectPindex;
      if (palette && Number.isInteger(pindex)) faceColor = palette[pindex] ?? null;
      if (faceColor === null) {
        const paint = Array.from(triangle.attributes).find(a => a.localName === 'paint_color' || a.localName === 'mmu_segmentation');
        const painted = paintedExtruder(paint?.value);
        if (painted) faceColor = filamentColors[painted - 1] ?? null;
      }
      triangleColors[faceIndex++] = faceColor;
      for (const key of ['v1', 'v2', 'v3']) {
        const vertexIndex = Number(triangle.getAttribute(key));
        if (!Number.isInteger(vertexIndex) || vertexIndex < 0 || vertexIndex >= points.length)
          throw Error('Triangle 3MF référençant un sommet inexistant.');
        const v = points[vertexIndex];
        coords[index++] = v[0]; coords[index++] = v[1]; coords[index++] = v[2];
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(coords, 3));
    geometry.applyMatrix4(new THREE.Matrix4().multiplyMatrices(unitMatrix, worldMatrix));
    const base = defaultColor ?? objectColor ?? filamentColors[slot - 1] ?? 0x5bc6eb;
    const paintFaces = {};
    for (let i = 0; i < triangleColors.length; i++) {
      const color = triangleColors[i];
      if (color !== null && color !== base) {
        paintFaces[i] = '#' + color.toString(16).padStart(6, '0').toUpperCase();
      }
    }
    geometries.push({ g: geometry, name: name.slice(0, 120), color: base,
      faceColors: Object.keys(paintFaces).length ? paintFaces : null });
  }

  function addObject(file, objectId, parentMatrix, depth = 0, inheritedSlot = null) {
    if (depth > 20) throw Error('Trop de niveaux de composants 3MF.');
    const key = file.path.toLowerCase() + '#' + objectId;
    if (active.has(key)) throw Error('Référence circulaire de pièces 3MF.');
    active.add(key);
    try {
      const object = findObject(file, objectId);
      const label = object.getAttribute('name') || fallbackName;
      const rawColor = object.getAttribute('displaycolor') || '';
      const color = hexColor(rawColor);
      const slot = partSlots.get(String(objectId)) || objectSlots.get(String(objectId)) || inheritedSlot || 1;
      const mesh = first(object, 'mesh');
      if (mesh) appendMesh(mesh, parentMatrix, label, color, file, object, slot);
      for (const component of children(first(object, 'components'), 'component')) {
        const childPath = localPath(component);
        const referenced = resolvePart(file, childPath);
        const next = new THREE.Matrix4().multiplyMatrices(parentMatrix, transform(component.getAttribute('transform')));
        addObject(referenced, component.getAttribute('objectid'), next, depth + 1, slot);
      }
    } finally {
      active.delete(key);
    }
  }

  try {
    const build = first(root.xml.documentElement, 'build');
    const items = children(build, 'item');
    if (!items.length) throw Error('Aucun élément à construire trouvé dans le projet 3MF.');
    for (const item of items) {
      const modelFile = resolvePart(root, localPath(item));
      addObject(modelFile, item.getAttribute('objectid'), transform(item.getAttribute('transform')));
    }
    if (!geometries.length) throw Error('Le projet 3MF ne contient aucune géométrie utilisable.');
    return geometries;
  } catch (error) {
    geometries.forEach(part => part.g.dispose());
    throw error;
  } finally {
    xmlCache.clear();
  }
}
