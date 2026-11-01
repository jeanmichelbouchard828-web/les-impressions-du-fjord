"""Admin-only archive of original Bambu Studio user presets.

Imports are backups/inspection records. They are NOT executable printer
instructions, verified Bambu machine profiles or machine-ready G-code.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from flask import Response, abort, jsonify, redirect, request, url_for

EXTENSIONS = {".json", ".bbscfg", ".bbsflmt", ".zip"}
MAX_UPLOAD = 8 * 1024 * 1024
MAX_ARCHIVE_FILES = 750
MAX_PRESET_BYTES = 512 * 1024
MAX_TOTAL_UNCOMPRESSED = 18 * 1024 * 1024

class PresetImportError(ValueError):
    pass


# Library organization only; not a statement of physical print readiness.
# SHA-256 identifies the exact curated file, not just a duplicated display name.
PREFERRED_SIGNATURES = frozenset(['58c7e63222d6e385f1c1593b719eb64f5702b6e442d8f2024b27893b5f835961','7ddb9f098c5e32885486fb4fa0a85c3cafd6a5acd626cf4f9d089660e53e62e3','93b4bc654a12810eb25f985ba6bc9f0a5a8c4fafabec137089aaf26834bc0241','617c9203c46fa32894da5db5f1f750cae1b7f7039149f2d0c84b23a89db7fae4','c34bfaf76018ecbe30457639ff5753798e8341fff0043fcaaac361ce254e7aa1','70e50104183fb045e2bb6738ca4038a52ad9ed1e48628444763c4d6393cafcf4','2f585053861d2a91e497b419984f870cd6d5ce15ed6a95b514108702c16a4bb1','c4444b90cba97134be2ac2deb32ad8ae65dfd9798a561b4bdcb4894d8cc127db','95a25ef382a6c6db47588d91a7049b51e3ed7c9642ba47d8eb4cd790724fede8','5f9c096525ae9666559a4d1a51f8b8c8437b5e6d666a49d5132852499ea9d58c'])
ALTERNATIVE_SIGNATURES = frozenset(['12e8c9fdf341cfb2ff5831968d515bd6bb39de40e94f362601c04f6b13f919cd','1e451aefcee77c06ac67128b51772b79f1a9a10bd15dd82ea6fbe1e195042958','a125956a1909701c4d405639dea0379db29a27e74aee9091da631f56b0a5dd6a','fecc557a6252b185032e598abbd47f2df79cfeaf980957d3bfecf64bc06b6ec2','622be63e2e98f687c710b0f45718f0c585a37e91fb4018e29b9c3701eae763a9','617f46444a1fc7f7132837f5287191cc22e66f6fa2308a64d2064bed567bece0'])

def profile_tier(signature):
    if signature in PREFERRED_SIGNATURES: return "essentiel"
    if signature in ALTERNATIVE_SIGNATURES: return "alternative"
    return "archive"

def _category(data, path):
    # Bambu Studio filenames and export bundles are not uniform across versions.
    declared = str(data.get("type") or data.get("preset_type") or "").lower()
    tokens = [declared] + [part.lower() for part in PurePosixPath(path).parts[:-1]]
    for token in tokens:
        if token in {"machine", "printer", "printers", "machines"}: return "Imprimante"
        if token in {"filament", "filaments", "material", "materials"}: return "Filament"
        if token in {"process", "print", "prints", "printing", "print_profile"}: return "Impression"
    keys = set(data)
    if keys.intersection({"filament_settings_id", "filament_type", "filament_flow_ratio", "filament_diameter", "nozzle_temperature", "filament_max_volumetric_speed"}):
        return "Filament"
    if keys.intersection({"print_settings_id", "layer_height", "sparse_infill_density", "wall_loops", "initial_layer_print_height", "line_width"}):
        return "Impression"
    if keys.intersection({"printer_settings_id", "printer_model", "nozzle_diameter", "machine_max_acceleration_x", "machine_start_gcode"}):
        return "Imprimante"
    return None

def _text(v, limit=140):
    if isinstance(v, list): v=v[0] if v else ""
    if not isinstance(v, str): v=str(v or "")
    return re.sub(r"[\x00-\x1f\x7f]", " ", v).strip()[:limit]

def _entry(data, path, source):
    if not isinstance(data, dict):
        return None
    category = _category(data, path)
    if not category:
        return None
    name = _text(data.get("name") or data.get("filament_settings_id") or
                 data.get("print_settings_id") or data.get("printer_settings_id") or
                 PurePosixPath(path).stem)
    if not name:
        return None
    # Preserve the complete numeric/array/string preset values unchanged.
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if len(serialized.encode("utf-8")) > MAX_PRESET_BYTES:
        raise PresetImportError("Un profil JSON est trop volumineux.")
    signature = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return {"name": name, "category": category, "source": _text(source, 230),
            "path": _text(path, 230), "settings": serialized, "signature": signature}

def parse_bambu_presets(filename: str, raw: bytes):
    """Parse JSON or ZIP-based Bambu user preset bundles without unpacking files."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_UPLOAD:
        raise PresetImportError("Fichier vide ou supérieur à 8 Mo.")
    suffix = PurePosixPath(filename.lower().replace("\\", "/")).suffix
    if suffix not in EXTENSIONS:
        raise PresetImportError("Format non pris en charge (.json, .bbscfg, .bbsflmt, .zip).")
    if suffix == ".json":
        try:
            doc = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PresetImportError("Profil JSON invalide.") from exc
        candidate = _entry(doc, filename, filename)
        if candidate is None:
            raise PresetImportError("Ce JSON ne contient pas de profil Bambu Studio identifiable.")
        return [candidate], 0

    try:
        source = zipfile.ZipFile(io.BytesIO(raw))
    except (zipfile.BadZipFile, OSError) as exc:
        raise PresetImportError("Ce bundle ne semble pas être une archive ZIP Bambu valide.") from exc
    with source as zf:
        files = zf.infolist()
        if len(files) > MAX_ARCHIVE_FILES:
            raise PresetImportError("Archive trop volumineuse (nombre de fichiers).")
        total = 0
        result = []
        skipped = 0
        for info in files:
            # Inspect metadata BEFORE touching member bytes; never unzip to disk.
            if info.is_dir():
                continue
            path = info.filename.replace("\\", "/")
            p = PurePosixPath(path)
            if not path or path.startswith("/") or any(part in ("..", "") for part in p.parts):
                raise PresetImportError("Chemin non autorisé dans l'archive.")
            if info.flag_bits & 0x1:
                raise PresetImportError("Les archives chiffrées ne sont pas prises en charge.")
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED:
                raise PresetImportError("Archive décompressée trop volumineuse.")
            if p.suffix.lower() != ".json":
                continue
            if info.file_size > MAX_PRESET_BYTES:
                skipped += 1
                continue
            try:
                with zf.open(info) as item:
                    b = item.read(MAX_PRESET_BYTES + 1)
                if len(b) > MAX_PRESET_BYTES:
                    skipped += 1
                    continue
                doc = json.loads(b.decode("utf-8-sig"))
                item = _entry(doc, path, filename)
                if item:
                    result.append(item)
                else:
                    skipped += 1
            except (UnicodeDecodeError, json.JSONDecodeError):
                skipped += 1
            except (RuntimeError, zipfile.BadZipFile, OSError) as exc:
                raise PresetImportError("Archive endommagée ou contenu inaccessible.") from exc
            if len(result) > MAX_ARCHIVE_FILES:
                raise PresetImportError("Nombre de profils trop élevé.")
    if not result:
        raise PresetImportError("Aucun profil Bambu reconnaissable dans l'archive.")
    # Eliminate duplicates within a single bundle.
    return list({item["signature"]: item for item in result}.values()), skipped

def register_bambu_preset_library(app, db, admin_required, verify, csrfinput, page):
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS bambu_user_presets(
          id BIGSERIAL PRIMARY KEY,
          name TEXT NOT NULL,
          category TEXT NOT NULL,
          source_file TEXT NOT NULL,
          internal_path TEXT NOT NULL,
          settings TEXT NOT NULL,
          signature TEXT NOT NULL UNIQUE,
          imported_at TIMESTAMPTZ DEFAULT NOW())""")

    @app.route("/admin/profils-bambu", methods=["GET", "POST"])
    @admin_required
    def bambu_preset_library():
        message = ""
        if request.method == "POST":
            verify()
            uploads = request.files.getlist("profiles")
            if not uploads or len(uploads) > 15:
                message = "Sélectionne de 1 à 15 fichiers d'export Bambu Studio."
            else:
                accepted, duplicate, ignored, errors = 0, 0, 0, []
                for upload in uploads:
                    fname = _text(upload.filename or "", 230)
                    try:
                        data = upload.stream.read(MAX_UPLOAD + 1)
                        entries, skips = parse_bambu_presets(fname, data)
                        ignored += skips
                        # Insert all profiles from one archive in a single parameterized
                        # PostgreSQL statement. Bundles with 600+ profiles must stay
                        # below the HTTP worker timeout, not do 600 DB round-trips.
                        payload = json.dumps(entries, ensure_ascii=False)
                        with db() as c:
                            inserted = c.execute("""INSERT INTO bambu_user_presets
                              (name, category, source_file, internal_path, settings, signature)
                              SELECT x.name,x.category,x.source,x.path,x.settings,x.signature
                              FROM jsonb_to_recordset(%s::jsonb)
                              AS x(name TEXT, category TEXT, source TEXT, path TEXT, settings TEXT, signature TEXT)
                              ON CONFLICT(signature) DO NOTHING
                              RETURNING id""", (payload,)).fetchall()
                        accepted += len(inserted)
                        duplicate += len(entries)-len(inserted)
                    except PresetImportError as exc:
                        errors.append(fname + " : " + str(exc))
                message = (f"{accepted} profil(s) importé(s), {duplicate} doublon(s) ignoré(s), "
                           f"{ignored} entrée(s) non reconnue(s).")
                if errors:
                    message += " Erreurs : " + "; ".join(errors[:8])
        with db() as c:
            items = c.execute("""SELECT id,name,category,source_file,internal_path,signature,imported_at
              FROM bambu_user_presets ORDER BY id DESC LIMIT 1000""").fetchall()
            counts = c.execute("""SELECT category,COUNT(*) AS total FROM bambu_user_presets
              GROUP BY category ORDER BY category""").fetchall()
        tiers = {"essentiel": 0, "alternative": 0, "archive": 0}
        for item in items:
            item["tier"] = profile_tier(item["signature"])
            tiers[item["tier"]] += 1
        items.sort(key=lambda item: ({"essentiel": 0, "alternative": 1, "archive": 2}[item["tier"]], item["name"].casefold()))
        default_tier = "essentiel" if tiers["essentiel"] else "tous"
        return page("Profils Bambu Studio", r"""
<h1>⚙️ Mes profils Bambu Studio</h1>
<p><a class="btn" href="/admin/atelier-3d">↩ Retour à mon Atelier 3D</a></p>
<p>Importer tes préréglages <strong>d'imprimante, de filament et d'impression</strong> pour les conserver dans l'espace administrateur.</p>
<p><strong>Important :</strong> les paramètres sont archivés tels quels. Leur importation ne remplace pas un tranchage compatible Bambu et ne lance aucune impression.</p>
<form method="post" enctype="multipart/form-data">
 {{csrf_field|safe}}
 <label>Mes exports Bambu Studio (.bbscfg, .bbsflmt, .zip ou .json)
  <input type="file" name="profiles" accept=".json,.bbscfg,.bbsflmt,.zip" multiple required>
 </label>
 <button type="submit">📥 Importer tous les fichiers sélectionnés</button>
 <p class="muted small">Jusqu'à 15 fichiers à la fois, 8 Mo par fichier et 10 Mo au total par envoi. Tu peux recommencer autant de fois que nécessaire. Les doublons identiques sont ignorés.</p>
</form>
{% if message %}<p role="status" class="card">{{message}}</p>{% endif %}
<h2>Mes profils classés</h2>
<p>Ce classement facilite le choix : <strong>aucun profil d'imprimante ou ancien essai n'est effacé automatiquement.</strong> Les profils essentiels et alternatifs restent <strong>à vérifier dans Bambu Studio</strong> avant toute impression.</p>
<p><strong>Essentiels : {{tiers.essentiel}}</strong> · Alternatives : {{tiers.alternative}} · Archives : {{tiers.archive}}</p>
{% for item in counts %}<span style="display:inline-block;margin:4px;padding:8px;border:1px solid #5b8199;border-radius:8px">{{item.category}} : <strong>{{item.total}}</strong></span>{% endfor %}
{% if items %}
<div class="row" style="align-items:end;flex-wrap:wrap">
<label style="min-width:180px">Afficher
<select id="fjordBambuTier" aria-label="Filtrer les profils par classement">
<option value="essentiel" {% if default_tier == 'essentiel' %}selected{% endif %}>⭐ Mes essentiels</option>
<option value="alternative">🧪 Alternatives à tester</option>
<option value="archive">📦 Archives / anciens essais</option>
<option value="tous" {% if default_tier == 'tous' %}selected{% endif %}>Tous les profils</option>
</select></label>
<label style="min-width:230px;flex:1">Rechercher un profil
<input id="fjordBambuSearch" type="search" placeholder="PETG, ASA, 0.12, SIGNATURE..." autocomplete="off">
</label>
</div>
<p id="fjordBambuFilteredCount" role="status" aria-live="polite"></p>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse">
<thead><tr><th style="text-align:left">Profil</th><th>Classement</th><th>Catégorie</th><th>Fichier d'origine</th><th>Action</th></tr></thead>
<tbody>
{% for item in items %}
<tr class="fjord-bambu-profile-row" data-tier="{{item.tier}}" data-name="{{item.name|lower}}" data-category="{{item.category|lower}}" style="border-top:1px solid #56758c">
<td style="padding:8px">{{item.name}}</td>
<td>{% if item.tier == 'essentiel' %}⭐ Essentiel (à vérifier){% elif item.tier == 'alternative' %}🧪 Alternative{% else %}📦 Archive{% endif %}</td>
<td>{{item.category}}</td><td>{{item.source_file}}</td>
<td><a href="/admin/profils-bambu/{{item.id}}.json">JSON</a>
<form style="display:inline" method="post" action="/admin/profils-bambu/{{item.id}}/supprimer" onsubmit="return confirm('Supprimer ce profil archivé ?')">
{{csrf_field|safe}}<button type="submit" aria-label="Supprimer {{item.name}}">✕</button>
</form></td>
</tr>{% endfor %}</tbody>
</table></div>
<script>
(function(){
 const tier=document.getElementById("fjordBambuTier");
 const query=document.getElementById("fjordBambuSearch");
 const output=document.getElementById("fjordBambuFilteredCount");
 const rows=Array.from(document.querySelectorAll(".fjord-bambu-profile-row"));
 function filter(){
   const kind=tier.value;
   const needle=query.value.trim().normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
   let shown=0;
   rows.forEach(row=>{
     const content=(row.dataset.name+" "+row.dataset.category).normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
     const visible=(kind==="tous"||row.dataset.tier===kind)&&(!needle||content.includes(needle));
     row.hidden=!visible;if(visible)shown++;
   });
   output.textContent=shown+" profil(s) affiché(s) sur "+rows.length+".";
 }
 tier.addEventListener("change",filter);query.addEventListener("input",filter);filter();
})();
</script>
<style>.fjord-bambu-profile-row[hidden]{display:none!important}</style>
{% else %}<p>Ta bibliothèque de profils est vide pour le moment.</p>{% endif %}
""", csrf_field=csrfinput(), message=message, counts=counts, items=items, tiers=tiers, default_tier=default_tier)

    @app.get("/admin/profils-bambu/<int:profile_id>.json")
    @admin_required
    def bambu_profile_download(profile_id):
        with db() as c:
            row = c.execute("SELECT settings,name FROM bambu_user_presets WHERE id=%s", (profile_id,)).fetchone()
        if row is None: abort(404)
        name = re.sub(r"[^a-zA-Z0-9_-]+", "_", row["name"])[:80] or "bambu_profile"
        return Response(row["settings"].encode("utf-8"), mimetype="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}.json"',
                                 "Cache-Control": "no-store"})

    @app.post("/admin/profils-bambu/<int:profile_id>/supprimer")
    @admin_required
    def bambu_profile_delete(profile_id):
        verify()
        with db() as c:
            c.execute("DELETE FROM bambu_user_presets WHERE id=%s", (profile_id,))
        return redirect(url_for("bambu_preset_library"))

    @app.get("/api/admin/atelier/profils")
    @admin_required
    def bambu_profile_list():
        with db() as c:
            rows = c.execute("SELECT id,name,category FROM bambu_user_presets ORDER BY category,name LIMIT 1000").fetchall()
        response = jsonify(profiles=[dict(row) for row in rows])
        response.headers["Cache-Control"] = "no-store"
        return response
