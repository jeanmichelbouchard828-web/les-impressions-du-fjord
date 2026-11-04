# Préparation de la migration vers Render — Les Impressions du Fjord

**État : uniquement une préproduction isolée, aucune bascule client.**

Railway continue à héberger le site et PostgreSQL de production. Ne rien
arrêter, écraser, supprimer ou redéployer sur Railway pendant ces tests.

## Infrastructure de préproduction prévue

- Site Render : `fjord-render-apercu-20261104`, Docker, branche
  `migration/render-fjord-20261104`, déploiement automatique désactivé.
- PostgreSQL Render : `fjord-render-apercu-db-20261104`, **nouvelle base vide**
  distincte de la base Railway et de la base SNIC.
- Fichier de configuration : `render.preview.yaml` (spécifique au test).
- Région envisagée : Oregon. Confirmer la conformité de traitement des données
  clients et l'incidence sur la latence avant le transfert réel.
- Coûts potentiels : service `1c-2g` et PostgreSQL `0.1c-256mb` sont des
  forfaits payants. **Ne pas provisionner sans approbation des frais et de
  l'espace de travail Render.** Les prix affichés lors de la création priment.

## Protections de la préproduction

1. `FJORD_PREVIEW_MODE=1` et une base **Render isolée** sont obligatoires.
   Le code de la branche de migration refuse les méthodes d'écriture ainsi que
   l'accès aux API, à l'administration, aux liens de paiement et aux webhooks
   Stripe. Il laisse les pages publiques et `/health` consultables.
2. Ne renseigner dans la préproduction **aucune** des variables Stripe,
   OctoEverywhere/Bambu, e-mail SMTP ni `ADMIN_SETUP_TOKEN` de production.
3. Ne jamais utiliser l'URL `DATABASE_URL` de Railway sur le Render de test;
   l'application crée/migre son schéma au démarrage et comptabilise les visites
   dans PostgreSQL.
4. Ne pas configurer le nouveau domaine public, les webhooks Stripe ni les
   liens des clients avant la vraie bascule.
5. Le fichier `render.preview.yaml` est uniquement une proposition de
   déploiement **séparée**. Ne pas fusionner cette branche ni la traiter comme
   un déploiement de production. Ne pas affecter `gestion-snic-render-complet`.

## Contrôles de réception de la préproduction

- [ ] Le conteneur Docker se construit avec PrusaSlicer et Bambu Studio;
      les profils X2D d'origine sont vérifiés.
- [ ] `/health` répond 200 et les pages publiques s'affichent sur PC/mobile.
- [ ] `POST /contact`, les routes `/admin`, `/api`,
      `/payer/stripe/*`, `/stripe/webhook` sont interdites en préproduction.
- [ ] Les tests de sécurité `tests/test_fjord_preview_guard.py` réussissent.
- [ ] Aucun compte client ni moyen de paiement réel ne se retrouve en
      préproduction.
- [ ] Railway reste l'unique base **en écriture**.

## Préparation de la vraie bascule (étape ultérieure, pas aujourd'hui)

1. Inventorier PostgreSQL Railway (version, extensions, tables, clés,
   utilisateurs, galerie/images BYTEA, 3MF, devis, paiements, statistiques).
2. Vérifier les sauvegardes et produire une sauvegarde cohérente **pg_dump**
   chiffrée sur un stockage privé, sans afficher les identifiants ni exposer
   de données de clients dans GitHub ou les journaux.
3. Prévoir une nouvelle base Render de production séparée de l'aperçu, sans
   données préexistantes. Tester une restauration sur une copie isolée avant
   toute intervention sur la production.
4. Prévoir une période de gel des écritures Railway, conserver les sites
   lisibles si possible, prendre la **sauvegarde finale après gel**, restaurer
   PostgreSQL vers Render, comparer schéma, nombres d'entrées et échantillons
   sécurisés, et tester intégrité et fichiers.
5. Garder Stripe et les notifications **sur le seul site principal**.
   Vérifier checkout, webhooks avec déduplication d'évènements, e-mails et
   suivi des commandes sur un environnement contrôlé; ne jamais émettre
   simultanément deux webhooks vers des bases indépendantes.
6. Vérifier l'Atelier 3D, les profils X2D et le parcours de tranchage sans
   lancement physique de machine en préproduction. Activer l'impression
   uniquement après validation de la sécurité et des autorisations.
7. Valider Render comme écriture principale, conserver Railway en secours
   gelé avec son volume PostgreSQL; tester une reprise contrôlée à partir
   des nouvelles données Render avant toute réouverture de Railway.

**Règle : rien supprimer — ni les applications, ni les services Postgres,
ni les disques, ni les sauvegardes.**
