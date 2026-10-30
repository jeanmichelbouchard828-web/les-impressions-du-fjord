// Imports geometry from multi-part 3MF packages exported by Bambu Studio,
// OrcaSlicer and PrusaSlicer (3MF Production Extension: p:path).
// This intentionally imports geometry and placement, not printer presets / G-code.
import * as THREE from 'three';
import { unzipSync, strFromU8 } from 'three/addons/libs/fflate.module.js';

const MAX_EXPANDED_BYTES = 80 * 1024 * 1024;
const MAX_TRIANGLES = 500000;
const MAX_OBJECTS = 100;
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
  // ZIP entries other than model XML are not needed for geometry-only import.
  // Check declared uncompressed sizes before expanding any archive member.
  let declaredSize = 0;
  const zip = unzipSync(new Uint8Array(arrayBuffer), {
    filter: entry => {
      if (!/\.model$/i.test(entry.name)) return false;
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
  if (!archive.size) throw Error('Aucun modèle 3D trouvé dans le fichier 3MF.');
  const load = path => {
    const entry = archive.get(normalized(path).toLowerCase());
    if (!entry) throw Error('Modèle référencé absent : ' + path);
    const cacheKey = entry.path.toLowerCase();
    if (!xmlCache.has(cacheKey)) xmlCache.set(cacheKey, parseXml(entry.bytes, entry.path));
    return { path: entry.path, xml: xmlCache.get(cacheKey) };
  };
  const byName = Array.from(archive.values());
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

  function appendMesh(mesh, worldMatrix, name, color) {
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
    let index = 0;
    for (const triangle of triangles) {
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
    geometries.push({ g: geometry, name: name.slice(0, 120), color });
  }

  function addObject(file, objectId, parentMatrix, depth = 0) {
    if (depth > 20) throw Error('Trop de niveaux de composants 3MF.');
    const key = file.path.toLowerCase() + '#' + objectId;
    if (active.has(key)) throw Error('Référence circulaire de pièces 3MF.');
    active.add(key);
    try {
      const object = findObject(file, objectId);
      const label = object.getAttribute('name') || fallbackName;
      const rawColor = object.getAttribute('displaycolor') || '';
      const color = /^#[0-9a-f]{6}/i.test(rawColor)
        ? parseInt(rawColor.slice(1, 7), 16) : 0x5bc6eb;
      const mesh = first(object, 'mesh');
      if (mesh) appendMesh(mesh, parentMatrix, label, color);
      for (const component of children(first(object, 'components'), 'component')) {
        const childPath = localPath(component);
        const referenced = resolvePart(file, childPath);
        const next = new THREE.Matrix4().multiplyMatrices(parentMatrix, transform(component.getAttribute('transform')));
        addObject(referenced, component.getAttribute('objectid'), next, depth + 1);
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
