# Préparation de la migration vers Render — Les Impressions du Fjord

**État : uniquement une préproduction isolée, aucune bascule client.**

Railway continue à héberger le site et PostgreSQL de production. Ne rien
arrêter, écraser, supprimer ou redéployer sur Railway pendant ces tests.

## Infrastructure de préproduction prévue

- Site Render : `fjord-render-apercu-20261104`, Docker, branche
  `migration/render-fjord-20261104`, déploiement automatique désactivé.
- PostgreSQL Render : `fjord-render-apercu-db-20261104`, **nouvelle base
  gratuite et temporaire vide**, distincte des bases Railway et SNIC. Son
  expiration après 30 jours et l'absence de sauvegardes la rendent impropre
  à la production : **aucune information client réelle ne doit y entrer**.
- Fichier de configuration : `render.preview.yaml` (spécifique au test).
- Région envisagée : Oregon. Confirmer la conformité de traitement des données
  clients et l'incidence sur la latence avant le transfert réel.
- Coût de cette préproduction : site Web Render Starter
  `0.5c-512mb` (~7 USD/mois) + PostgreSQL Render `free` (0 USD pendant
  l'essai). Vérifier le tarif affiché, les limites et toute consommation
  additionnelle avant la création; l'espace Render nécessite une confirmation.
- Conteneur `Dockerfile.render-lite` : sans PrusaSlicer ni Bambu Studio. Le
  site, le suivi et l'atelier public se chargent; le tranchage automatique
  et les véritables envois X2D ne sont **pas disponibles** sur cette préproduction.
  Il faudra une passerelle locale sécurisée vers le PC Windows avant de
  considérer cette architecture équivalente au Docker complet.
- La **production économique visée** utilise PostgreSQL Railway déjà payé.
  Cela requiert un endpoint réseau sécurisé de Railway vers Render, le
  chiffrage TLS, une gestion prudente des secrets et peut occasionner de
  l'egress payant. **Ne jamais utiliser la base Railway dans la préproduction.**

## Protections de la préproduction

1. `FJORD_PREVIEW_MODE=1` et une base **Render isolée** sont obligatoires.
   Avant la moindre requête SQL, la préproduction refuse toute base extérieure
   à Render et exige un nom de base commençant par `fjord_render_apercu`.
   Elle refuse aussi les secrets Stripe, OctoEverywhere et d'initialisation admin.
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

- [ ] Le conteneur Docker **léger** se construit sans PrusaSlicer ni Bambu Studio.
      Les dépendances X2D sont volontairement indisponibles en préproduction.
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
