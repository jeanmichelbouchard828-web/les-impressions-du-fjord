"""Vitrine commerciale Les Impressions du Fjord, sans modifier le flux des commandes."""
MARKETING_CSS = r"""<style>
/* Vitrine : lisibilite, confiance et conversion, sans bibliotheques externes. */
.fjm-home{overflow:clip;display:flex;flex-direction:column}
.fjm-home>.fjm-hero{order:0}
.fjm-home>#realisations{order:1}
.fjm-home>#atelier{order:2}
.fjm-home>#services{order:3}
.fjm-home>.fji-section{order:4}
.fjm-home>#fonctionnement{order:5}
.fjm-home>#questions{order:6}
.fjm-home>.fjord-board{order:7}
.fjm-home>.fjm-final{order:8}
.fjm-hero{position:relative;isolation:isolate;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(245px,.65fr);align-items:center;gap:clamp(22px,4vw,60px);padding:clamp(27px,5vw,66px)!important;margin-bottom:16px;min-height:430px;background:radial-gradient(circle at 80% 18%,#1579ab75,transparent 41%),linear-gradient(120deg,#0d304e,#071a30 70%)!important;border:1px solid #368bb5;border-radius:24px;box-shadow:0 20px 55px #0004}
.fjm-kicker{display:block;font-weight:850;letter-spacing:.13em;text-transform:uppercase;color:#80e2ff;font-size:12px}
.fjm-hero h1{font-size:clamp(36px,5.5vw,70px)!important;line-height:1.04!important;letter-spacing:-.055em;margin:16px 0 18px;max-width:930px}
.fjm-accent{color:#6cddff}
.fjm-hero-lead{max-width:650px;font-size:clamp(16px,1.8vw,21px);line-height:1.6;color:#d3e8f5}
.fjm-hero-actions{display:flex;flex-wrap:wrap;gap:11px;margin-top:25px;align-items:center}
.fjm-hero-actions .btn{min-height:52px;padding:13px 22px;text-align:center;white-space:normal}
.fjm-hero-actions .fjm-outline{background:#0e2b42!important;border-color:#59c6ea!important;color:#effaff!important}
.fjm-points{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 0;padding:0;list-style:none}
.fjm-points li{padding:8px 12px;border:1px solid #347593;border-radius:99px;background:#0e334bbb;color:#d5f2ff;font-size:12px;font-weight:750}
.fjm-hero-panel{padding:23px;border-radius:21px;border:1px solid #4285a8;background:#061b2bdc;box-shadow:0 15px 45px #0003}
.fjm-hero-panel img{width:89px;height:89px;object-fit:cover;border-radius:18px;box-shadow:0 0 24px #0abdf555}
.fjm-hero-panel h2{color:#f1fbff;margin:15px 0 8px;font-size:clamp(22px,2.4vw,29px)}
.fjm-hero-panel p{margin:0 0 18px;color:#c6dfec;font-size:15px}
.fjm-hero-panel a{font-weight:800;text-decoration:underline;text-underline-offset:4px}
.fjm-hero-proof{padding:16px!important;border-color:#49a6c8!important;background:linear-gradient(145deg,#08243b,#061726)!important}
.fjm-hero-photo-grid{display:grid;grid-template-columns:1.16fr .84fr;gap:9px;align-items:stretch}
.fjm-hero-photo-grid a{display:block;min-width:0;overflow:hidden;border:1px solid #397e9e;border-radius:13px;background:#071625}
.fjm-hero-photo-grid img{display:block;width:100%!important;height:clamp(120px,17vw,195px)!important;object-fit:cover;border-radius:12px!important;box-shadow:none!important;transition:transform .25s ease}
.fjm-hero-photo-grid a:hover img{transform:scale(1.035)}
.fjm-proof-eyebrow{margin:14px 0 3px!important;color:#82e2fa!important;font-size:10px!important;font-weight:900;letter-spacing:.14em}
.fjm-hero-proof h2{margin:4px 0 6px!important;font-size:clamp(19px,2vw,25px)!important}
.fjm-hero-proof>p:last-child{margin:0!important}
body.light .fjm-hero-proof{background:linear-gradient(145deg,#fff,#e9f7fd)!important}
body.light .fjm-proof-eyebrow{color:#087fa9!important}
@media(max-width:1050px){.fjm-hero-photo-grid img{height:clamp(150px,28vw,240px)!important}}
@media(max-width:690px){.fjm-hero-photo-grid{grid-template-columns:1.1fr .9fr;gap:7px}.fjm-hero-photo-grid img{height:clamp(130px,42vw,190px)!important}.fjm-hero-proof{padding:12px!important}}
.fjm-section{margin:clamp(26px,4vw,52px) 0}
.fjm-home>#atelier{margin:0 0 28px;order:2}
.fjm-atelier{position:relative;display:grid;grid-template-columns:72px minmax(0,1fr) auto;align-items:center;gap:20px;padding:22px 25px;border:1px solid #46bfe6;border-radius:20px;overflow:hidden;background:radial-gradient(circle at 8% 50%,#0f9bc54a,transparent 32%),linear-gradient(110deg,#103b57,#0a2238 72%);box-shadow:0 16px 38px #00132155}
.fjm-atelier-mark{display:grid;place-items:center;width:68px;height:68px;border:1px solid #65d5f3;border-radius:19px;background:linear-gradient(145deg,#167aa0,#0b3b59);font-size:34px;box-shadow:0 0 28px #21b8e533}
.fjm-atelier-copy{min-width:0}
.fjm-atelier-copy .fjm-kicker{font-size:10px}
.fjm-atelier-copy h2{margin:5px 0 5px;color:#f0fbff;font-size:clamp(19px,2.5vw,27px);line-height:1.2}
.fjm-atelier-copy p{margin:0;color:#c7e2ee;font-size:14px;line-height:1.5;max-width:66ch}
.fjm-atelier-actions{display:flex;align-items:center;gap:13px;flex-wrap:wrap;margin-top:13px}
.fjm-atelier-actions .btn{min-height:43px;padding:10px 16px;background:linear-gradient(110deg,#7be8ff,#26bbe7)!important;border:1px solid #a0efff!important;color:#05283a!important;font-size:14px;font-weight:900}
.fjm-atelier-secondary{font-size:13px;font-weight:800;color:#d8f5ff;text-underline-offset:4px}
.fjm-atelier-note{display:grid;gap:4px;min-width:126px;padding:13px 15px;border:1px solid #347b9a;border-radius:13px;background:#071d2d99;color:#e8f8ff}
.fjm-atelier-note strong{font-size:12px}
.fjm-atelier-note span{font-size:11px;color:#9dd8ed}
body.light .fjm-atelier{background:linear-gradient(110deg,#e4f7ff,#c9ebfa);border-color:#73c4e2;box-shadow:0 14px 32px #0b719a18}
body.light .fjm-atelier-copy h2{color:#153d53}
body.light .fjm-atelier-copy p,body.light .fjm-atelier-secondary{color:#315e74}
body.light .fjm-atelier-mark{background:linear-gradient(145deg,#b8eaff,#e8f8ff);border-color:#93cce3}
body.light .fjm-atelier-note{background:#f7fcff;border-color:#b2d9e9;color:#174861}
body.light .fjm-atelier-note span{color:#3a7087}
@media(max-width:760px){.fjm-home>#atelier{margin-bottom:20px}.fjm-atelier{grid-template-columns:54px minmax(0,1fr);gap:13px;padding:17px;border-radius:16px}.fjm-atelier-mark{width:52px;height:52px;border-radius:14px;font-size:27px}.fjm-atelier-note{grid-column:2;display:flex;align-items:center;gap:8px;min-width:0;width:fit-content;padding:7px 10px}.fjm-atelier-note strong{font-size:11px}.fjm-atelier-note span{font-size:11px}}
@media(max-width:460px){.fjm-atelier{grid-template-columns:1fr;gap:10px}.fjm-atelier-mark{width:46px;height:46px;font-size:24px}.fjm-atelier-note{grid-column:1}.fjm-atelier-actions{display:grid;grid-template-columns:1fr}.fjm-atelier-actions .btn{text-align:center}.fjm-atelier-secondary{text-align:center}}

.fjm-heading{max-width:800px;margin-bottom:23px}
.fjm-ready-count{display:inline-flex;align-items:center;width:fit-content;max-width:100%;margin:0 0 12px;padding:7px 11px;border:1px solid #62c98d;border-radius:999px;background:#113b30;color:#b6f5ce;font-size:12px;font-weight:850;line-height:1.3}
body.light .fjm-ready-count{background:#e8f8ed;color:#17623b;border-color:#a6dbb8}

.fjm-heading h2{margin:8px 0 10px;font-size:clamp(27px,3.5vw,40px)}
.fjm-heading p{margin:0}
.fjm-services{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.fjm-service{display:grid;grid-template-columns:40px 1fr;grid-template-rows:auto auto;align-items:center;column-gap:12px;row-gap:2px;padding:13px;border:1px solid #2f7098;border-radius:14px;background:linear-gradient(150deg,#15364d,#0c2235)}
.fjm-service .fjm-icon{grid-row:1/3;display:grid;place-items:center;width:40px;height:40px;border-radius:12px;background:#16577a;font-size:20px}
.fjm-service h3{font-size:16px;margin:0;color:#edfbff}.fjm-service p{font-size:12px;line-height:1.35;margin:0}
.fjm-service a{margin-top:0;padding-top:2px;font-size:12px;font-weight:850;text-decoration:underline;text-underline-offset:3px}
.fjm-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.fjm-step{padding:14px;border:1px solid #306f91;border-radius:14px;background:#0d273c}
.fjm-step-number{display:grid;place-items:center;width:37px;height:37px;border:1px solid #50bde9;border-radius:12px;color:#90e9ff;font-weight:900}
.fjm-step h3{font-size:16px;color:#ebfaff;margin:9px 0 5px}
.fjm-step p{margin:0;font-size:12px;line-height:1.4}
.fjm-project-content .fjm-photo-real-badge,.fjm-project-content .fjm-photo-render-badge{display:inline-flex;align-items:center;width:max-content;max-width:100%;padding:5px 9px;border-radius:99px;font-size:11px;font-weight:800;line-height:1.3;text-transform:none;letter-spacing:0}.fjm-project-content .fjm-photo-real-badge{border:1px solid #5ecb93;background:#123f35;color:#a9f4ca}.fjm-project-content .fjm-photo-render-badge{border:1px solid #639bc1;background:#15344c;color:#c5e7fb}.fjm-project-image-link img{transition:transform .25s ease}.fjm-project:hover .fjm-project-image-link img{transform:scale(1.025)}
.fjm-gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px}
.fjm-project{display:flex;flex-direction:column;min-width:0;overflow:hidden;border:1px solid #2c7396;border-radius:18px;background:#102e43;color:#eefaff!important;text-decoration:none!important;transition:border-color .15s,transform .15s}
.fjm-project:hover{border-color:#69d6f6;transform:translateY(-2px)}
.fjm-project img{display:block;width:100%;height:210px;object-fit:cover;background:#16344a}
.fjm-project .fjm-project-noimage{display:grid;place-items:center;height:210px;background:linear-gradient(135deg,#1d5275,#0b273c);font-size:48px}
.fjm-project-content{padding:17px}.fjm-project-content span{display:block;color:#80d8f4;font-size:11px;text-transform:uppercase;letter-spacing:.1em;font-weight:750}
.fjm-project-content strong{display:block;margin:7px 0;font-size:17px;overflow-wrap:anywhere}
.fjm-project-content small{font-size:13px;color:#c3dce9;font-weight:750}.fjm-model-available{display:block;margin:8px 0;color:#8de6b2!important;font-size:12px!important;font-weight:800}.fjm-project-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}.fjm-project-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:8px 12px;border:1px solid #56bfe5;border-radius:10px;color:#e9f9ff;font-size:13px;font-weight:800;text-decoration:none;background:#0a263a}.fjm-project-actions a:last-child{background:#70d7f1;color:#08283a;border-color:#70d7f1}.fjm-project-actions a:hover{filter:brightness(1.12)}
.fjm-section-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}
.fjm-faq{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}
.fjm-faq details{padding:17px 19px;border:1px solid #326f8b;border-radius:14px;background:#0d293d}
.fjm-faq summary{cursor:pointer;font-size:15px;font-weight:800;color:#e5f8ff}
.fjm-faq details p{margin:12px 0 0;font-size:14px}
.fjm-final{padding:clamp(22px,4vw,46px);margin:58px 0 0;border:1px solid #3c9fc6;border-radius:23px;background:linear-gradient(115deg,#105077,#0a263d);display:flex;justify-content:space-between;align-items:center;gap:26px}
.fjm-final h2{margin:0 0 8px;color:#f2fbff}.fjm-final p{margin:0}.fjm-final .btn{flex-shrink:0;white-space:normal;text-align:center}
.fjord-model-ready{display:table;width:fit-content;max-width:100%;margin:14px 0;padding:8px 12px;border:1px solid #58c78c;border-radius:999px;background:#103c30;color:#b6f5ce;font-size:13px;font-weight:800;line-height:1.35}
body.light .fjord-model-ready{background:#e8f8ed;color:#17623b;border-color:#a6dbb8}
.fjord-gallery-detail-cta{display:flex;flex-wrap:wrap;align-items:stretch;gap:12px;margin:22px 0}
.fjord-gallery-detail-cta>.btn,.fjord-gallery-detail-cta>button{display:flex;flex:1 1 220px;min-width:min(100%,220px);min-height:54px;align-items:center;justify-content:center;text-align:center;white-space:normal;line-height:1.25}
.fjord-gallery-detail-cta>.secondary-btn,.fjord-gallery-detail-cta>.fjord-share-project{border:1px solid #4a91b6!important;background:#163e59!important;color:#f2faff!important;font-weight:800}
.fjord-gallery-detail-cta>.fjord-share-project{border-radius:10px;padding:13px 20px;cursor:pointer;font:inherit}
.fjord-gallery-detail-cta>.secondary-btn:hover,.fjord-gallery-detail-cta>.fjord-share-project:hover{background:#215b7d!important}
.fjord-gallery-detail-cta .fjord-share-result{flex-basis:100%;color:#b6f5ce;font-size:14px}
body.light .fjord-gallery-detail-cta>.secondary-btn,body.light .fjord-gallery-detail-cta>.fjord-share-project{background:#e5f5fd!important;color:#17425b!important;border-color:#8dbed5!important}
@media(max-width:640px){.fjord-gallery-detail-cta{display:grid;grid-template-columns:1fr;gap:9px}.fjord-gallery-detail-cta>.btn,.fjord-gallery-detail-cta>button{width:100%;min-width:0;min-height:48px;padding:12px 15px}}
.fjm-gallery-controls{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:22px;align-items:center}
.fjm-gallery-controls input{max-width:360px;min-width:200px;margin:0}
.fjm-filter{min-height:42px;padding:9px 14px;border:1px solid #4285a5;border-radius:99px;background:#0e3249;color:#e8f9ff;font:inherit;font-size:14px;cursor:pointer}
.fjm-filter[aria-pressed=true]{background:#097cae;color:white;border-color:#88dafa}
.fjm-gallery-empty{padding:20px;border:1px solid #346481;border-radius:15px;margin-top:15px}
.fjm-quote-helper{max-width:690px;padding:16px 18px;border:1px solid #347d9f;border-radius:14px;background:#0b2a42;margin:18px 0 24px}
.fjm-quote-helper strong{color:#d8f5ff}.fjm-quote-helper p{margin:6px 0 0;font-size:14px}
.fjm-quote-helper ul{margin:8px 0 0;padding-left:20px;color:#c6dce9;font-size:14px}
.fjm-quote-form{padding:clamp(18px,3vw,30px);max-width:700px;border:1px solid #32779d;border-radius:18px;background:#0c273c}
.fjm-quote-form .fjm-form-submit{width:100%;min-height:52px}
.fjm-quote-note{font-size:13px;margin:10px 0 0}
body.light .fjm-hero{background:linear-gradient(130deg,#e6f7ff,#c1e9fd)!important;border-color:#80bee0}
body.light .fjm-hero h1,body.light .fjm-hero-panel h2,body.light .fjm-step h3,body.light .fjm-service h3,body.light .fjm-final h2{color:#14394f!important}
body.light .fjm-accent{color:#077fae}
body.light .fjm-hero-lead,body.light .fjm-hero-panel p{color:#315b73}
body.light .fjm-kicker{color:#056997}
body.light .fjm-hero-panel,body.light .fjm-service,body.light .fjm-step,body.light .fjm-faq details,body.light .fjm-quote-helper,body.light .fjm-quote-form{background:#fff;border-color:#b4d8e9}
body.light .fjm-points li{background:#e5f5fd;border-color:#a5d0e4;color:#265c78}
body.light .fjm-service .fjm-icon{background:#d7effa}
body.light .fjm-project{background:#fff;color:#17425b!important}
body.light .fjm-project-content small{color:#376b82}
body.light .fjm-faq summary,body.light .fjm-quote-helper strong{color:#164863}
body.light .fjm-filter{background:#fff;color:#1b4c67}
body.light .fjm-filter[aria-pressed=true]{background:#087cae;color:#fff}
body.light .fjm-final{background:linear-gradient(110deg,#dbf2ff,#b3e4fb)}
@media(max-width:1050px){.fjm-services{grid-template-columns:repeat(2,minmax(0,1fr))}.fjm-hero{grid-template-columns:1fr}.fjm-hero-panel{display:block;padding:16px}.fjm-hero-panel h2{margin:0 0 5px}}
@media(max-width:690px){.fjm-hero{padding:25px 18px!important;min-height:0}.fjm-hero h1{font-size:clamp(35px,9vw,53px)!important}.fjm-hero-actions{display:grid;grid-template-columns:1fr}.fjm-hero-actions a{width:100%}.fjm-hero-panel{padding:16px}.fjm-steps,.fjm-gallery{grid-template-columns:1fr 1fr}.fjm-project img,.fjm-project .fjm-project-noimage{height:155px}.fjm-faq{grid-template-columns:1fr}.fjm-final{display:block}.fjm-final .btn{margin-top:18px;width:100%}}
@media(max-width:460px){.fjm-services,.fjm-steps,.fjm-gallery{grid-template-columns:1fr}.fjm-project img,.fjm-project .fjm-project-noimage{height:230px}.fjm-service{padding:11px}.fjm-gallery-controls input{width:100%;max-width:100%;min-width:0}}
@media(prefers-reduced-motion:reduce){.fjm-project{transition:none}}

/* Real workshop pieces are presented as a touch-friendly sales carousel. */
.fjm-showcase{position:relative}
.fjm-showcase-toolbar{display:flex;align-items:center;justify-content:flex-end;gap:8px;margin:0 0 12px}
.fjm-showcase-toolbar button{min-width:42px;min-height:42px;border:1px solid #66b4d5;border-radius:11px;background:#123b56;color:#f2fbff;font:inherit;font-size:22px;font-weight:800;cursor:pointer}
.fjm-showcase-toolbar button:hover:not(:disabled){background:#17668a}
.fjm-showcase-toolbar button:disabled{opacity:.45;cursor:not-allowed}
.fjm-showcase-toolbar button:focus-visible,.fjm-featured-track:focus-visible{outline:3px solid #a5efff;outline-offset:3px}
#fjmFeaturedCounter{min-width:70px;text-align:center;color:#d8edf7;font-size:13px;font-weight:800;font-variant-numeric:tabular-nums}
.fjm-home .fjm-featured-track{display:flex;gap:15px;overflow-x:auto;overscroll-behavior-inline:contain;scroll-snap-type:x mandatory;scroll-padding:2px;scrollbar-width:thin;padding:2px 2px 13px;scroll-behavior:smooth}
.fjm-home .fjm-featured-track .fjm-project{flex:0 0 calc((100% - 30px)/3);scroll-snap-align:start;scroll-snap-stop:always}
.fjm-home .fjm-featured-track .fjm-project[hidden]{display:none!important}
body.light .fjm-showcase-toolbar button{background:#fff;color:#174963;border-color:#a3cbdf}
body.light #fjmFeaturedCounter{color:#28556e}
@media(max-width:1000px){.fjm-home .fjm-featured-track .fjm-project{flex-basis:calc((100% - 15px)/2)}}
@media(max-width:650px){.fjm-showcase-toolbar{justify-content:center}.fjm-home .fjm-featured-track .fjm-project{flex-basis:100%}}
@media(prefers-reduced-motion:reduce){.fjm-home .fjm-featured-track{scroll-behavior:auto!important}}
.fjm-home .fjm-project-image-link{display:block;color:inherit;text-decoration:none}
.fjm-home .fjm-project-content{display:flex;flex-direction:column;gap:8px;flex:1}
.fjm-home .fjm-project-content strong{margin:0}
.fjm-home .fjm-project-model-state{min-height:34px;color:#b9d6e3;font-size:12px;line-height:1.4}
.fjm-home .fjm-project-actions{display:grid;grid-template-columns:1fr;gap:8px;margin-top:auto;padding-top:9px}
.fjm-home .fjm-project-actions a{display:flex;align-items:center;justify-content:center;min-height:43px;padding:9px 11px;border:1px solid #448caf;border-radius:10px;background:#10344b;color:#eafaff;text-align:center;text-decoration:none;font-size:13px;font-weight:800;line-height:1.35}
.fjm-home .fjm-project-actions .fjm-project-quote{background:#0786b8;border-color:#54c7ee;color:#fff}
.fjm-home .fjm-project-actions a:hover{filter:brightness(1.15)}
.fjm-home .fjm-project-actions a:focus-visible{outline:3px solid #a5efff;outline-offset:2px}
body.light .fjm-home .fjm-project-model-state{color:#365d72}
body.light .fjm-home .fjm-project-actions a{background:#edf8fd;color:#194963;border-color:#9cc9dd}
body.light .fjm-home .fjm-project-actions .fjm-project-quote{background:#087dab;color:#fff;border-color:#087dab}
/* Hero commercial plus visible : vraie photo, promesse claire et CTA dominant. */
.fjm-hero{border-color:#45c8ef!important;box-shadow:0 24px 68px #00111f80,inset 0 1px 0 #b2edff20!important}
.fjm-hero-proof{border-color:#58c8e8!important;box-shadow:0 20px 48px #00111f88,inset 0 1px 0 #b2edff18!important}
.fjm-hero-photo-grid img{height:clamp(150px,19vw,220px)!important}
.fjm-hero-actions .btn:first-child{background:linear-gradient(115deg,#86efff,#32c9f0 58%,#08a4d8)!important;border:1px solid #a9f5ff!important;color:#03263a!important;box-shadow:0 10px 30px #05bce655!important;font-weight:900;letter-spacing:.01em}
.fjm-hero-actions .btn:first-child:hover{filter:brightness(1.08);box-shadow:0 12px 34px #05bce677!important}
.fjm-hero h1{ text-wrap:balance}
body.light .fjm-hero{box-shadow:0 24px 58px #0a719a24,inset 0 1px 0 #fff!important}
body.light .fjm-hero-proof{box-shadow:0 15px 34px #0a719a20!important}
body.light .fjm-hero-actions .btn:first-child{background:linear-gradient(115deg,#06a6d7,#087eb2)!important;color:#fff!important;border-color:#62c8e9!important}
@media(max-width:690px){.fjm-hero-photo-grid img{height:clamp(140px,39vw,190px)!important}.fjm-hero-actions{margin-top:19px}}
.fjm-process-strip{display:flex;align-items:center;justify-content:center;gap:10px 16px;flex-wrap:wrap;margin:27px 0 0;padding:14px 17px;border:1px solid #2d6989;border-radius:14px;background:#0b2438;color:#e9f7ff}
.fjm-process-label{width:100%;color:#78d9f5;font-size:10px;font-weight:900;letter-spacing:.12em;text-align:center}
.fjm-process-strip strong{font-size:13px;line-height:1.35}.fjm-process-arrow{color:#63d5f2;font-weight:900}
.fjm-final{margin-top:22px!important;padding:16px 21px!important;border-radius:15px!important;gap:14px!important}
.fjm-final .fjm-kicker{display:none}.fjm-final h2{font-size:clamp(19px,2.5vw,26px)!important;margin:0!important}.fjm-final p{display:none}
.fjm-final .btn{min-height:44px;padding:10px 16px}
body.light .fjm-process-strip{background:#fff;border-color:#c2dce9;color:#214d65}body.light .fjm-process-label{color:#087dab}
@media(max-width:650px){.fjm-process-strip{display:grid;grid-template-columns:1fr;justify-items:start;gap:7px;margin-top:20px}.fjm-process-label{text-align:left}.fjm-process-arrow{display:none}.fjm-process-strip strong{font-size:13px}.fjm-final{display:flex!important;align-items:stretch!important;flex-direction:column!important}.fjm-final .btn{width:100%;margin:0!important}}

/* Accueil vendeur et équilibré : accroche courte, photo réelle et chemin d’achat clair. */
.fjm-home .fjm-hero{grid-template-columns:minmax(0,1.18fr) minmax(260px,.82fr);min-height:0;padding:clamp(24px,4vw,48px)!important;margin-bottom:18px;gap:clamp(22px,3.5vw,44px)}
.fjm-home .fjm-hero-proof{display:block!important;padding:12px;background:#061626b8;border:1px solid #348bb3;border-radius:18px;box-shadow:0 12px 30px #0003}
.fjm-home .fjm-hero>div{max-width:none}
.fjm-home .fjm-hero h1{max-width:13ch;font-size:clamp(40px,5vw,64px);line-height:1.02;margin:12px 0}
.fjm-home .fjm-hero-lead{max-width:50ch;margin-bottom:18px}
.fjm-home .fjm-points{display:none}
.fjm-home .fjm-hero-actions{display:flex;flex-direction:row!important;align-items:center;flex-wrap:nowrap;gap:10px}
.fjm-home .fjm-hero-actions .btn{white-space:nowrap;padding:13px 16px;font-size:14px}
.fjm-home .fjm-hero-photo-grid{grid-template-columns:1.1fr .9fr!important;grid-template-rows:220px!important;grid-auto-rows:220px!important;height:220px!important;min-height:0!important}
.fjm-home .fjm-hero-photo-grid>a{display:block;width:100%;height:220px!important;min-height:0!important}
.fjm-home .fjm-hero-photo-grid img{display:block;width:100%;height:220px!important;max-height:none!important;min-height:0!important;object-fit:cover}
.fjm-home .fjm-proof-eyebrow{margin:12px 4px 4px}
.fjm-home .fjm-hero-proof h2{font-size:clamp(18px,2vw,24px);margin:4px}
.fjm-home .fjm-hero-proof>p:last-child{margin:4px;font-size:14px}
.fjm-home #realisations{margin-top:18px}
.fjm-home #realisations .fjm-heading{max-width:760px;margin-bottom:16px}
@media(max-width:760px){.fjm-home .fjm-hero{grid-template-columns:minmax(0,1fr);padding:24px 20px!important;border-radius:18px}.fjm-home .fjm-hero h1{font-size:clamp(40px,10vw,54px)}.fjm-home .fjm-hero-proof{display:none!important}.fjm-home .fjm-hero-actions{display:grid;grid-template-columns:1fr;flex-direction:column!important;flex-wrap:wrap}.fjm-home .fjm-hero-actions .btn{width:100%;white-space:normal;text-align:center}.fjm-home #realisations{margin-top:12px}}

/* Présentation plus concentrée du formulaire de soumission sur grand écran. */
@media(min-width:980px){body.fjord-public main:has(.fjm-quote-form){max-width:960px!important}}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form{width:100%;max-width:760px!important}
/* Conversion refresh: clearer purchase paths, real catalogue imagery and more useful project guidance. */
.fjm-home{gap:0}
.fjm-home .fjm-hero{min-height:450px;grid-template-columns:minmax(0,1.12fr) minmax(290px,.88fr);gap:clamp(24px,4vw,54px);padding:clamp(28px,4vw,56px)!important}
.fjm-home .fjm-hero h1{max-width:11ch;font-size:clamp(44px,5.5vw,74px);line-height:.99;letter-spacing:-.06em}
.fjm-home .fjm-hero h1 .fjm-accent{display:block;color:#6cddff}
.fjm-home .fjm-hero-lead{max-width:54ch;font-size:clamp(17px,1.65vw,20px)}
.fjm-home .fjm-hero-sub{margin:11px 0 0;color:#b7d3e2;font-size:13px}
.fjm-home .fjm-hero-actions .btn:first-child{min-height:54px;padding:13px 20px;font-size:15px}
.fjm-home .fjm-hero-actions .fjm-outline{background:transparent!important;color:#e8f9ff!important}
.fjm-home .fjm-hero-proof{padding:14px!important}
.fjm-home .fjm-hero-photo-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:clamp(150px,18vw,220px);height:auto!important;min-height:0!important}
.fjm-home .fjm-hero-photo-grid>a{height:auto!important;min-height:150px!important}
.fjm-home .fjm-hero-photo-grid img{height:100%!important;min-height:150px!important;max-height:none!important;aspect-ratio:1/1;object-fit:cover}
.fjm-home .fjm-hero-photo-placeholder{display:grid;place-items:center;min-height:150px;border:1px dashed #4384a0;border-radius:13px;background:#0a263b;color:#a9dced;font-weight:800;text-align:center}
.fjm-home .fjm-offers{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}
.fjm-home .fjm-offer{display:flex;flex-direction:column;min-height:220px;padding:21px;border:1px solid #2e7191;border-radius:17px;background:linear-gradient(150deg,#12344d,#0b2033);transition:transform .18s,border-color .18s,box-shadow .18s}
.fjm-home .fjm-offer:hover{transform:translateY(-3px);border-color:#59c8e9;box-shadow:0 13px 27px #00152266}
.fjm-home .fjm-offer-icon{display:grid;place-items:center;width:43px;height:43px;border:1px solid #448db0;border-radius:13px;background:#124769;color:#b5efff;font-size:20px}
.fjm-home .fjm-offer h3{margin:14px 0 6px;color:#f0fbff;font-size:17px}
.fjm-home .fjm-offer p{margin:0 0 14px;color:#bfd5e2;font-size:13px;line-height:1.55}
.fjm-home .fjm-offer a{margin-top:auto;color:#83e1fa;font-size:13px;font-weight:850;text-decoration:underline;text-underline-offset:3px}
.fjm-home .fjm-faq{grid-template-columns:repeat(2,minmax(0,1fr))}
.fjm-home .fjm-faq summary{list-style:none;display:flex;align-items:center;justify-content:space-between;gap:15px}
.fjm-home .fjm-faq summary::-webkit-details-marker{display:none}
.fjm-home .fjm-faq summary:after{content:"+";flex:0 0 26px;display:grid;place-items:center;width:26px;height:26px;border:1px solid #367997;border-radius:50%;color:#83e1fa;font-size:20px;line-height:1}
.fjm-home .fjm-faq details[open] summary:after{content:"−"}
.fjm-home .fjm-faq details p{max-width:64ch}
.fjm-home .fjm-final{box-shadow:0 18px 44px #00111f55}
body.light .fjm-home .fjm-offer{background:linear-gradient(150deg,#fff,#eaf6fc);border-color:#b4d8e8}
body.light .fjm-home .fjm-offer h3{color:#173d54}
body.light .fjm-home .fjm-offer p{color:#466679}
body.light .fjm-home .fjm-offer-icon{background:#e4f5fc;color:#12648a;border-color:#aad6e8}
body.light .fjm-home .fjm-hero-actions .fjm-outline{background:#fff!important;color:#15516e!important;border-color:#8dbbd1!important}
body.light .fjm-home .fjm-hero-sub{color:#426276}
@media(max-width:980px){.fjm-home .fjm-offers{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){.fjm-home .fjm-hero{grid-template-columns:1fr;min-height:0;padding:26px 21px!important}.fjm-home .fjm-hero h1{font-size:clamp(44px,10vw,62px)}.fjm-home .fjm-hero-proof{display:block!important}.fjm-home .fjm-hero-photo-grid{grid-auto-rows:clamp(145px,35vw,210px)}.fjm-home .fjm-hero-actions{display:grid;grid-template-columns:1fr}.fjm-home .fjm-hero-actions .btn{width:100%;white-space:normal}.fjm-home .fjm-faq{grid-template-columns:1fr}}
@media(max-width:460px){.fjm-home .fjm-offers{grid-template-columns:1fr}.fjm-home .fjm-offer{min-height:0}.fjm-home .fjm-hero h1{font-size:44px}}

/* Parcours d'achat : actions faciles à trouver, filtres clairs et formulaire lisible. */
.fjm-gallery-controls select{min-height:42px;max-width:260px;margin:0;padding:9px 34px 9px 13px;border:1px solid #4285a5;border-radius:12px;background:#0e3249;color:#e8f9ff;font:inherit;font-size:14px}
.fjm-gallery-controls select:focus-visible,.fjm-gallery-controls input:focus-visible,.fjm-filter:focus-visible,.fjm-project-actions a:focus-visible,.fjm-quote-form :focus-visible{outline:3px solid #81e2ff;outline-offset:2px}
.fjm-project[hidden]{display:none!important}
.fjm-project-actions a{flex:1 1 125px}
.fjm-quote-helper{box-shadow:0 8px 25px #00152222}
.fjm-quote-form{box-shadow:0 15px 38px #00152233}
.fjm-quote-form>label{margin-top:15px}
.fjm-quote-form>label:first-of-type{margin-top:0}
.fjm-quote-form input:not([type=file]),.fjm-quote-form select,.fjm-quote-form textarea{min-height:46px}
.fjm-quote-form textarea{min-height:150px;resize:vertical}
.fjm-quote-options{margin:15px 0 18px;border:1px solid #397b99;border-radius:13px;background:#091f31}
.fjm-quote-options summary{padding:13px 15px;cursor:pointer;color:#a6e9fb;font-weight:800;line-height:1.4}
.fjm-quote-options[open] summary{border-bottom:1px solid #397b99}
.fjm-quote-options>.fjord-brief{margin:14px 14px 18px}
.fjm-quote-options>label{display:grid;margin:13px 15px;gap:6px}
.fjm-quote-options>label:last-of-type{margin-bottom:17px}
.fjm-quote-options select,.fjm-quote-options input{width:100%}
.fjm-quote-start{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0 22px;max-width:900px}
.fjm-quote-start a{display:flex;flex-direction:column;justify-content:center;gap:5px;min-height:78px;padding:13px 15px;border:1px solid #3985a7;border-radius:14px;background:linear-gradient(145deg,#123950,#0a263b);color:#effaff!important;font-weight:850;text-decoration:none!important;transition:border-color .15s,transform .15s}
.fjm-quote-start a:hover{transform:translateY(-2px);border-color:#7be8ff}
.fjm-quote-start a span{color:#b6d8e6;font-size:12px;font-weight:500;line-height:1.4}
.fjm-quote-start a strong{font-size:14px;color:#effaff}
body.light .fjm-quote-start a{background:linear-gradient(145deg,#fff,#eaf7fc);border-color:#add3e3;color:#173e54!important}
body.light .fjm-quote-start a span{color:#456a7e}
body.light .fjm-quote-start a strong{color:#173e54}
.fjord-breadcrumbs{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 18px;color:#a9c6d7;font-size:13px}
.fjord-breadcrumbs a{color:#8de4ff;text-decoration:underline;text-underline-offset:3px}
.fjord-breadcrumbs [aria-current=page]{color:#eaf8ff;overflow-wrap:anywhere}
body.light .fjord-breadcrumbs{color:#527185}
body.light .fjord-breadcrumbs a{color:#087da5}
body.light .fjord-breadcrumbs [aria-current=page]{color:#173e54}
@media(max-width:760px){.fjm-quote-start{grid-template-columns:1fr;gap:8px}.fjm-quote-start a{min-height:64px}}
body.light .fjm-quote-options{background:#f2faff;border-color:#add3e3}
body.light .fjm-quote-options summary{color:#155b79}
body.light .fjm-quote-options[open] summary{border-color:#add3e3}
.fjm-quote-form .fjm-form-submit{margin-top:18px;border-radius:12px;font-size:16px;font-weight:850;box-shadow:0 8px 20px #005b7844;transition:transform .15s,filter .15s}
.fjm-quote-form .fjm-form-submit:hover:not(:disabled){transform:translateY(-1px);filter:brightness(1.07)}
.fjm-gallery-empty{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:18px 20px}
.fjm-gallery-empty[hidden]{display:none!important}
.fjm-gallery-empty a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 15px;border-radius:10px;background:#70d7f1;color:#08283a!important;font-weight:850;text-decoration:none}
.fjm-nextsteps{max-width:760px;margin:24px 0;padding:20px 22px;border:1px solid #397b99;border-radius:16px;background:linear-gradient(145deg,#0d2c42,#092237)}
.fjm-nextsteps h2{margin:0 0 12px;color:#effaff;font-size:21px}
.fjm-nextsteps ol{display:grid;gap:9px;margin:0;padding-left:22px;color:#c8e0ec}
body.light .fjm-nextsteps{background:linear-gradient(145deg,#fff,#eaf7fc);border-color:#add3e3}
body.light .fjm-nextsteps h2{color:#173e54}
body.light .fjm-nextsteps ol{color:#31586d}
.fjord-mobile-quote-cta{display:none}
@media(max-width:760px){
 body:has(.fjord-mobile-quote-cta){padding-bottom:calc(78px + env(safe-area-inset-bottom,0px))}
 .fjord-mobile-quote-cta{position:fixed;z-index:999;left:12px;right:12px;bottom:max(10px,env(safe-area-inset-bottom,0px));display:flex;justify-content:center;align-items:center;min-height:52px;padding:12px 18px;border:1px solid #a0efff;border-radius:14px;background:linear-gradient(110deg,#79e6ff,#25b8e5);box-shadow:0 10px 30px #00142188;color:#05283a!important;font-size:15px;font-weight:900;text-align:center;text-decoration:none!important}
 .fjm-gallery-controls{display:grid;grid-template-columns:1fr 1fr;align-items:stretch}
 .fjm-gallery-controls input,.fjm-gallery-controls select{grid-column:1/-1;width:100%;max-width:none}
 .fjm-filter{min-height:46px;padding:8px 10px;font-size:13px}
 .fjm-project-actions a{flex-basis:100%;min-height:46px}
}
/* Mobile storefront: lead with a real printed part, then a short path to order. */
@media(max-width:640px){
 .fjm-home .fjm-hero{display:grid;grid-template-columns:minmax(0,1fr);gap:0;padding:18px 16px 17px!important;margin:0 -1px 14px;border-radius:20px;background:radial-gradient(ellipse at 82% 0%,#126f9b88,transparent 52%),linear-gradient(155deg,#0d304b,#071a2c 72%)!important;border-color:#45c8ef!important;box-shadow:0 16px 42px #00111f77!important}
 .fjm-home .fjm-hero>div{display:contents}
 .fjm-home .fjm-hero .fjm-kicker{grid-row:1;font-size:10px;letter-spacing:.12em}
 .fjm-home .fjm-hero h1{grid-row:2;max-width:12ch;margin:9px 0 13px;font-size:clamp(39px,11vw,49px)!important;line-height:.99;letter-spacing:-.055em}
 .fjm-home .fjm-hero-proof{display:block!important;grid-row:3;margin:0 0 14px;padding:8px!important;border-radius:15px;background:#061727!important}
 .fjm-home .fjm-hero-photo-grid{grid-template-columns:1fr!important;grid-template-rows:190px!important;grid-auto-rows:190px!important;height:190px!important;overflow:hidden;border-radius:11px}
 .fjm-home .fjm-hero-photo-grid>a{grid-column:1;grid-row:1;width:100%;height:190px!important;min-height:190px!important}
 .fjm-home .fjm-hero-photo-grid>a:nth-child(n+2){display:none}
 .fjm-home .fjm-hero-photo-grid img{width:100%;height:190px!important;min-height:190px!important;object-fit:cover}
 .fjm-home .fjm-proof-eyebrow{margin:9px 3px 2px!important;font-size:9px!important}
 .fjm-home .fjm-hero-proof h2{margin:3px!important;font-size:17px!important}
 .fjm-home .fjm-hero-proof>p:last-child{display:none}
 .fjm-home .fjm-hero-lead{grid-row:4;margin:0 0 12px;font-size:15px;line-height:1.48;color:#d9edf7}
 .fjm-home .fjm-hero-actions{grid-row:5;display:grid;grid-template-columns:1fr;gap:8px;margin:0}
 .fjm-home .fjm-hero-actions .btn{width:100%;min-height:48px;padding:11px 13px;white-space:normal;text-align:center;font-size:14px}
 .fjm-home .fjm-hero-sub{grid-row:6;margin:10px 0 0;font-size:12px;line-height:1.45;color:#b7d8e9}
 .fjm-home .fjm-points{display:none}
 .fjm-home #atelier{margin-top:15px}
 .fjm-home .fjm-atelier{padding:15px;border-radius:17px}
 .fjm-home #services{margin-top:25px}
 .fjm-home .fjm-heading{margin-bottom:13px}
 .fjm-home .fjm-offer{padding:16px;border-radius:15px}
 .fjm-home #realisations{margin-top:25px}
}
@media(prefers-reduced-motion:reduce){.fjm-project,.fjm-project img,.fjm-quote-form .fjm-form-submit{transition:none!important}}
/* Nouvelle identité visuelle : atelier de fabrication, papier chaud, sapin et argile. */
body.fjord-public{--fj-ink:#17251f;--fj-pine:#1d3329;--fj-pine-soft:#2a4537;--fj-paper:#f5f1e7;--fj-paper-card:#fffdf7;--fj-clay:#dc6242;--fj-clay-light:#ff9772;--fj-sage:#c9d7b8;--fj-muted:#696f62;--fj-line:#d9ddcf;--fj-radius:20px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
body.fjord-public:not(.light){--fjord-bg:#111a15;--fjord-surface:#1b2820;--fjord-surface-2:#26382d;--fjord-text:#f5f1e7;--fjord-muted:#c8cbbf;--fjord-line:#405546;--fjord-accent:#ff8a62;--fjord-accent-2:#d6e2bf;background:radial-gradient(ellipse at 82% -5%,#b75b3833,transparent 36%),linear-gradient(160deg,#111a15,#17241c 55%,#111a15)!important;color:var(--fjord-text)!important}
body.fjord-public.light{--fjord-bg:#f5f1e7;--fjord-surface:#fffdf7;--fjord-surface-2:#ece9dc;--fjord-text:#17251f;--fjord-muted:#58675c;--fjord-line:#d9ddcf;--fjord-accent:#c94f31;--fjord-accent-2:#2e674e;background:#f5f1e7!important;color:#17251f!important}
body.fjord-public :is(h1,h2,h3){font-family:Georgia,"Times New Roman",serif;letter-spacing:-.035em}
body.fjord-public main{color:var(--fjord-text)}
body.fjord-public:not(.light) main h1,body.fjord-public:not(.light) main h2,body.fjord-public:not(.light) main h3{color:#f7f2e7;text-shadow:none}
body.fjord-public.light main h1,body.fjord-public.light main h2,body.fjord-public.light main h3{color:#173329;text-shadow:none}
body.fjord-public:not(.light) main p{color:#c9cbbf}
body.fjord-public.light main p{color:#526258}
body.fjord-public .site-header{background:#14231cf2!important;border-bottom:1px solid #4a6552!important;box-shadow:0 8px 24px #09120d33!important}
body.fjord-public .site-header .brand{color:#f7f2e7!important}
body.fjord-public .site-header .brand-blue{color:#f59a74!important}
body.fjord-public .site-header .fjord-brand-tagline{color:#cbd5c2!important}
body.fjord-public .site-header nav a{color:#e0e4d7!important;border-radius:12px}
body.fjord-public .site-header nav a:hover,body.fjord-public .site-header nav a[aria-current=page]{background:#2a4233!important;border-color:#71866b!important;color:#fffdf7!important}
body.fjord-public .site-header nav a.nav-ready-cta,body.fjord-public .site-header nav a.nav-atelier-cta{background:#dc6242!important;border-color:#dc6242!important;color:#fffaf2!important;box-shadow:0 6px 18px #9c3c2733!important}
body.fjord-public .site-header .pref-controls select,body.fjord-public .site-nav-toggle{border-color:#73816e!important;border-radius:12px!important;background:#203229!important;color:#f5f1e7!important}
body.fjord-public.light .site-header{background:#fffdf7f2!important;border-color:#d9ddcf!important;box-shadow:0 8px 24px #3b4d3a12!important}
body.fjord-public.light .site-header .brand{color:#173329!important}
body.fjord-public.light .site-header .brand-blue{color:#bf4e32!important}
body.fjord-public.light .site-header .fjord-brand-tagline{color:#637066!important}
body.fjord-public.light .site-header nav a{color:#315345!important}
body.fjord-public.light .site-header nav a:hover,body.fjord-public.light .site-header nav a[aria-current=page]{background:#e9eee2!important;border-color:#bdc9b5!important;color:#173329!important}
body.fjord-public.light .site-header nav a.nav-ready-cta,body.fjord-public.light .site-header nav a.nav-atelier-cta{background:#c94f31!important;border-color:#c94f31!important;color:#fff!important}
body.fjord-public.light .site-header .pref-controls select,body.fjord-public.light .site-nav-toggle{background:#fffdf7!important;color:#173329!important;border-color:#bdc9b5!important}
body.fjord-public .fjord-side-nav{background:linear-gradient(180deg,#13251b,#1d3329)!important;border-color:#506b56!important}
body.fjord-public .fjord-side-menu a{color:#f5f1e7!important}
body.fjord-public .fjord-side-menu a[aria-current=page],body.fjord-public .fjord-side-menu a:hover{background:#355540!important;border-color:#8ea184!important}
body.fjord-public.light .fjord-side-nav{background:linear-gradient(180deg,#e9eee2,#dfe7d8)!important;border-color:#c3cebb!important}
body.fjord-public.light .fjord-side-menu a{color:#254638!important}
body.fjord-public.light .fjord-side-menu a[aria-current=page],body.fjord-public.light .fjord-side-menu a:hover{background:#fffdf7!important;color:#173329!important;border-color:#bdc9b5!important}
body.fjord-public main :is(.card,.gallery-tile,.tracking-result,.fjm-project,.fjm-service,.fjm-offer,.fjm-step,.fjm-faq details,.fjm-quote-helper,.fjm-quote-form,.contact-section,.atelier-feature,.fjord-support-panel,.fjord-board){border-color:#405546!important;border-radius:20px!important;background:linear-gradient(145deg,#1b2a21,#17251d)!important;box-shadow:0 12px 28px #08110b35!important}
body.fjord-public.light main :is(.card,.gallery-tile,.tracking-result,.fjm-project,.fjm-service,.fjm-offer,.fjm-step,.fjm-faq details,.fjm-quote-helper,.fjm-quote-form,.contact-section,.atelier-feature,.fjord-support-panel,.fjord-board){border-color:#d9ddcf!important;background:#fffdf7!important;box-shadow:0 10px 28px #394a3512!important}
body.fjord-public main .fjm-home .fjm-hero{border:1px solid #526d56!important;border-radius:28px!important;background:radial-gradient(ellipse at 86% 14%,#dc62424a,transparent 36%),linear-gradient(125deg,#243d2e,#14251c 73%)!important;box-shadow:0 26px 60px #08120b55!important}
body.fjord-public main .fjm-home .fjm-hero h1{color:#fff8e9!important}
body.fjord-public main .fjm-home .fjm-accent{color:#e9bd7d!important}
body.fjord-public main .fjm-home .fjm-kicker{color:#d4dfbd!important}
body.fjord-public main .fjm-home .fjm-hero-lead{color:#eee9dc!important}
body.fjord-public main .fjm-home .fjm-hero-proof{border-color:#526d56!important;background:#18281e!important}
body.fjord-public main .fjm-home .fjm-hero-proof h2{color:#f5f1e7!important}
body.fjord-public main .fjm-home .fjm-hero-proof p{color:#c8d0c1!important}
body.fjord-public main .fjm-home .fjm-hero-actions .btn:first-child,body.fjord-public main .fjm-home .fjm-final .btn,body.fjord-public main .fjm-atelier-actions .btn{background:#dc6242!important;border:1px solid #dc6242!important;color:#fffaf2!important;box-shadow:0 8px 20px #8f3b2833!important}
body.fjord-public main .fjm-home .fjm-hero-actions .fjm-outline{background:#293e30!important;border-color:#809076!important;color:#f6f2e8!important}
body.fjord-public.light main .fjm-home .fjm-hero{background:radial-gradient(ellipse at 88% 10%,#e26c4740,transparent 38%),linear-gradient(125deg,#e7eadc,#f4eddd)!important;border-color:#c9d0b9!important;box-shadow:0 20px 48px #4c573d16!important}
body.fjord-public.light main .fjm-home .fjm-hero h1{color:#173329!important}
body.fjord-public.light main .fjm-home .fjm-accent{color:#a9482e!important}
body.fjord-public.light main .fjm-home .fjm-kicker{color:#4f694d!important}
body.fjord-public.light main .fjm-home .fjm-hero-lead{color:#405347!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof{background:#fffdf7!important;border-color:#d3d7c9!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof h2{color:#173329!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof p{color:#526258!important}
body.fjord-public.light main .fjm-home .fjm-hero-actions .fjm-outline{background:#fffdf7!important;border-color:#a7b49f!important;color:#294d3b!important}
body.fjord-public main :is(.btn,button,input[type=submit],.atelier-cta){border-radius:14px!important;background:#dc6242!important;border-color:#dc6242!important;color:#fffaf2!important;box-shadow:0 7px 18px #8f3b2830!important;font-weight:800}
body.fjord-public main :is(.btn,button,input[type=submit],.atelier-cta):hover{filter:brightness(1.08);transform:translateY(-1px)}
body.fjord-public main .secondary-btn,body.fjord-public main .fjm-project-actions a:not(:last-child){background:#314b38!important;border-color:#799074!important;color:#f7f2e7!important}
body.fjord-public.light main .secondary-btn,body.fjord-public.light main .fjm-project-actions a:not(:last-child){background:#eef0e6!important;border-color:#bbc7b2!important;color:#254638!important}
body.fjord-public main a:not(.btn):not(.fjm-project):not(.fjord-mobile-quote-cta){color:#f59a74}
body.fjord-public.light main a:not(.btn):not(.fjm-project):not(.fjord-mobile-quote-cta){color:#a9432c}
body.fjord-public main :is(input,textarea,select){border-color:#607360!important;border-radius:12px!important;background:#14231a!important;color:#f8f4e9!important}
body.fjord-public.light main :is(input,textarea,select){border-color:#c0cabb!important;background:#fffdf7!important;color:#173329!important}
body.fjord-public main :is(input,textarea,select):focus-visible{outline:3px solid #e9bd7d!important;border-color:#e9bd7d!important}
body.fjord-public main :is(th,thead){background:#2d4835!important;color:#f5f1e7!important}
body.fjord-public.light main :is(th,thead){background:#e6ebdd!important;color:#254638!important}
body.fjord-public .fjord-visitor-counter{border-color:#526d56!important;border-radius:14px!important;background:#1b2a21!important;color:#e0e6d7!important}
body.fjord-public .fjord-visitor-counter strong{color:#f59a74!important}
body.fjord-public.light .fjord-visitor-counter{background:#fffdf7!important;color:#315345!important}
body.fjord-public>footer{border-color:#435a48!important;background:#111c16!important;color:#d4d5c9!important}
body.fjord-public>footer a{color:#f3a17e!important}
body.fjord-public.light>footer{border-color:#d9ddcf!important;background:#e9e7dc!important;color:#45584d!important}
body.fjord-public.light>footer a{color:#a9432c!important}
body.fjord-public .fjord-mobile-quote-cta{border-color:#e78360!important;background:linear-gradient(115deg,#df6848,#c94f31)!important;color:#fffaf2!important;box-shadow:0 10px 28px #5f2a1d55!important}
body.fjord-public :is(a,button,input,textarea,select):focus-visible{outline-color:#e9bd7d!important}
@media(max-width:760px){body.fjord-public .fjord-mobile-quote-cta{min-height:54px;border-radius:16px!important}body.fjord-public main .fjm-home .fjm-hero{border-radius:22px!important}body.fjord-public main .fjm-home .fjm-hero-actions .btn{min-height:50px}}
/* Electric studio redesign: kinetic purple, laser cyan and a lime order signal. */
body.fjord-public{--e-ink:#f5f7ff;--e-muted:#b8c1d7;--e-bg:#080b15;--e-panel:#111729;--e-panel2:#171f34;--e-border:#303b59;--e-violet:#8b5cff;--e-cyan:#35e1ff;--e-lime:#d8ff43;--e-radius:22px;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
body.fjord-public:not(.light){--fjord-bg:#080b15;--fjord-surface:#111729;--fjord-surface-2:#171f34;--fjord-text:#f5f7ff;--fjord-muted:#b8c1d7;--fjord-line:#303b59;--fjord-accent:#d8ff43;--fjord-accent-2:#35e1ff;background:radial-gradient(ellipse at 8% 4%,#782fff28,transparent 32%),radial-gradient(ellipse at 88% 16%,#00c9f629,transparent 30%),linear-gradient(155deg,#080b15,#0c1120 52%,#080b15)!important;color:#f5f7ff!important}
body.fjord-public.light{--fjord-bg:#f4f5fb;--fjord-surface:#fff;--fjord-surface-2:#eceefa;--fjord-text:#17172b;--fjord-muted:#555d78;--fjord-line:#d8dbee;--fjord-accent:#638e00;--fjord-accent-2:#087bba;background:radial-gradient(ellipse at 8% 0%,#c8b6ff55,transparent 30%),radial-gradient(ellipse at 92% 20%,#a6f4ff70,transparent 31%),#f4f5fb!important;color:#17172b!important}
body.fjord-public :is(h1,h2,h3){font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Arial,sans-serif;font-weight:850;letter-spacing:-.045em}
body.fjord-public:not(.light) main :is(h1,h2,h3){color:#f5f7ff;text-shadow:none}
body.fjord-public.light main :is(h1,h2,h3){color:#17172b;text-shadow:none}
body.fjord-public:not(.light) main p{color:#c0c9df}
body.fjord-public.light main p{color:#555d78}
body.fjord-public .site-header{background:#090d1bf2!important;border-bottom:1px solid #3a315f!important;box-shadow:0 8px 28px #03040b88!important}
body.fjord-public .site-header .brand{color:#f5f7ff!important}
body.fjord-public .site-header .brand-blue{color:#d8ff43!important;text-shadow:0 0 20px #d8ff4360!important}
body.fjord-public .site-header .fjord-brand-tagline{color:#b8c1d7!important}
body.fjord-public .site-header nav a{color:#cbd4ec!important;border-radius:12px!important}
body.fjord-public .site-header nav a:hover,body.fjord-public .site-header nav a[aria-current=page]{background:#1c2340!important;border-color:#51457c!important;color:#fff!important}
body.fjord-public .site-header nav a.nav-ready-cta,body.fjord-public .site-header nav a.nav-atelier-cta{background:#d8ff43!important;border-color:#edff9a!important;color:#11150a!important;box-shadow:0 0 18px #d8ff4344!important}
body.fjord-public .site-header .pref-controls select,body.fjord-public .site-nav-toggle{border-color:#55517c!important;border-radius:12px!important;background:#141a2c!important;color:#f5f7ff!important}
body.fjord-public.light .site-header{background:#fffefaed!important;border-color:#d9d9ed!important;box-shadow:0 8px 28px #29204a12!important}
body.fjord-public.light .site-header .brand{color:#17172b!important}
body.fjord-public.light .site-header .brand-blue{color:#608d00!important;text-shadow:none!important}
body.fjord-public.light .site-header .fjord-brand-tagline{color:#5a607a!important}
body.fjord-public.light .site-header nav a{color:#373650!important}
body.fjord-public.light .site-header nav a:hover,body.fjord-public.light .site-header nav a[aria-current=page]{background:#efedff!important;border-color:#d2c9f6!important;color:#241b48!important}
body.fjord-public.light .site-header nav a.nav-ready-cta,body.fjord-public.light .site-header nav a.nav-atelier-cta{background:#d8ff43!important;border-color:#badc45!important;color:#17172b!important}
body.fjord-public.light .site-header .pref-controls select,body.fjord-public.light .site-nav-toggle{background:#fff!important;color:#24213d!important;border-color:#d2c9f6!important}
body.fjord-public .fjord-side-nav{background:linear-gradient(180deg,#0e1020,#15182e)!important;border-color:#40356c!important}
body.fjord-public .fjord-side-menu a{color:#e4e8f8!important}
body.fjord-public .fjord-side-menu a[aria-current=page],body.fjord-public .fjord-side-menu a:hover{background:linear-gradient(100deg,#5430a5,#234c8d)!important;border-color:#8b5cff!important}
body.fjord-public.light .fjord-side-nav{background:linear-gradient(180deg,#efedff,#e4eaff)!important;border-color:#d4d4ed!important}
body.fjord-public.light .fjord-side-menu a{color:#302a4a!important}
body.fjord-public.light .fjord-side-menu a[aria-current=page],body.fjord-public.light .fjord-side-menu a:hover{background:#fff!important;color:#302064!important;border-color:#b9a8f4!important}
body.fjord-public main :is(.card,.gallery-tile,.tracking-result,.fjm-project,.fjm-service,.fjm-offer,.fjm-step,.fjm-faq details,.fjm-quote-helper,.fjm-quote-form,.contact-section,.atelier-feature,.fjord-support-panel,.fjord-board){border:1px solid #343c5c!important;border-radius:20px!important;background:linear-gradient(145deg,#151c31,#101626)!important;box-shadow:0 14px 34px #02040c77!important}
body.fjord-public.light main :is(.card,.gallery-tile,.tracking-result,.fjm-project,.fjm-service,.fjm-offer,.fjm-step,.fjm-faq details,.fjm-quote-helper,.fjm-quote-form,.contact-section,.atelier-feature,.fjord-support-panel,.fjord-board){border-color:#dedff0!important;background:linear-gradient(145deg,#fff,#f6f5ff)!important;box-shadow:0 12px 30px #33266d12!important}
body.fjord-public main .fjm-home .fjm-hero{position:relative;isolation:isolate;overflow:hidden;border:1px solid #48407a!important;border-radius:30px!important;background:radial-gradient(ellipse at 88% 14%,#8b5cff78,transparent 36%),radial-gradient(ellipse at 8% 100%,#00c9f638,transparent 38%),linear-gradient(125deg,#1b1735,#0f192d 72%)!important;box-shadow:0 28px 75px #03030caa,0 0 36px #6d48d422!important;animation:electric-breathe 8s ease-in-out infinite}
body.fjord-public main .fjm-home .fjm-hero h1{color:#fbfaff!important}
body.fjord-public main .fjm-home .fjm-accent{background:linear-gradient(95deg,#d8ff43 0%,#53edff 52%,#a98aff 100%);background-clip:text;-webkit-background-clip:text;color:transparent!important;-webkit-text-fill-color:transparent}
body.fjord-public main .fjm-home .fjm-kicker{color:#9df1ff!important}
body.fjord-public main .fjm-home .fjm-hero-lead{color:#dbe2f5!important}
body.fjord-public main .fjm-home .fjm-hero-proof{border-color:#4d4b84!important;background:linear-gradient(145deg,#151a30,#101522)!important;box-shadow:0 16px 40px #02040c88,0 0 25px #8b5cff22!important}
body.fjord-public main .fjm-home .fjm-hero-proof h2{color:#f5f7ff!important}
body.fjord-public main .fjm-home .fjm-hero-proof p{color:#c1cbe1!important}
body.fjord-public main .fjm-home .fjm-proof-eyebrow{color:#8fefff!important}
body.fjord-public.light main .fjm-home .fjm-hero{background:radial-gradient(ellipse at 86% 10%,#a98aff66,transparent 35%),radial-gradient(ellipse at 8% 100%,#7cecff55,transparent 38%),linear-gradient(125deg,#eeebff,#e8faff 72%)!important;border-color:#c9c1f4!important;box-shadow:0 22px 60px #33266d22!important}
body.fjord-public.light main .fjm-home .fjm-hero h1{color:#17172b!important}
body.fjord-public.light main .fjm-home .fjm-accent{background:linear-gradient(95deg,#4d7600,#008cb5 52%,#7250cf 100%);background-clip:text;-webkit-background-clip:text;color:transparent!important;-webkit-text-fill-color:transparent}
body.fjord-public.light main .fjm-home .fjm-kicker{color:#4c4788!important}
body.fjord-public.light main .fjm-home .fjm-hero-lead{color:#34374f!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof{background:#fffefa!important;border-color:#d7d4ec!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof h2{color:#17172b!important}
body.fjord-public.light main .fjm-home .fjm-hero-proof p{color:#555d78!important}
body.fjord-public main .fjm-home .fjm-hero-actions .btn:first-child,body.fjord-public main .fjm-home .fjm-final .btn,body.fjord-public main .fjm-atelier-actions .btn{background:linear-gradient(110deg,#e1ff59,#b6ef27)!important;border:1px solid #f1ff9e!important;color:#101506!important;box-shadow:0 8px 22px #a5db2944,0 0 20px #d8ff432b!important;font-weight:900}
body.fjord-public main .fjm-home .fjm-hero-actions .fjm-outline{background:#21213b!important;border-color:#7161a5!important;color:#f5f3ff!important}
body.fjord-public.light main .fjm-home .fjm-hero-actions .fjm-outline{background:#fffefa!important;border-color:#c5bce9!important;color:#30264f!important}
body.fjord-public main :is(.btn,button,input[type=submit],.atelier-cta){border-radius:14px!important;background:linear-gradient(110deg,#e1ff59,#b6ef27)!important;border:1px solid #f1ff9e!important;color:#101506!important;box-shadow:0 7px 20px #a5db2938!important;font-weight:850}
body.fjord-public main :is(.btn,button,input[type=submit],.atelier-cta):hover{filter:brightness(1.06);box-shadow:0 9px 26px #c0ff5555,0 0 20px #c0ff5533!important;transform:translateY(-2px)}
body.fjord-public main .secondary-btn,body.fjord-public main .fjm-project-actions a:not(:last-child){background:#202740!important;border-color:#58557f!important;color:#e8e9ff!important}
body.fjord-public.light main .secondary-btn,body.fjord-public.light main .fjm-project-actions a:not(:last-child){background:#efedff!important;border-color:#d1c9f0!important;color:#342b5c!important}
body.fjord-public main a:not(.btn):not(.fjm-project):not(.fjord-mobile-quote-cta){color:#64eaff}
body.fjord-public.light main a:not(.btn):not(.fjm-project):not(.fjord-mobile-quote-cta){color:#176b96}
body.fjord-public main :is(input,textarea,select){border-color:#464f74!important;border-radius:13px!important;background:#0d1423!important;color:#f6f7ff!important}
body.fjord-public.light main :is(input,textarea,select){border-color:#d0d2e9!important;background:#fff!important;color:#17172b!important}
body.fjord-public main :is(input,textarea,select):focus-visible{outline:3px solid #35e1ff!important;border-color:#35e1ff!important;box-shadow:0 0 0 4px #35e1ff20!important}
body.fjord-public main :is(th,thead){background:#272846!important;color:#f1f0ff!important}
body.fjord-public.light main :is(th,thead){background:#e9e6ff!important;color:#29264a!important}
body.fjord-public .fjm-home{gap:17px}
body.fjord-public .fjm-home>#services{order:1!important;margin:10px 0 20px!important;padding:clamp(18px,3vw,34px);border:1px solid #34395f;border-radius:26px;background:linear-gradient(135deg,#101626,#141b2f)!important}
body.fjord-public .fjm-home>#realisations{order:2!important;margin:8px 0 22px!important;padding:clamp(18px,3vw,34px);border:1px solid #37405f;border-radius:26px;background:linear-gradient(130deg,#101728,#101a24)!important}
body.fjord-public .fjm-home>#atelier{order:3!important;margin:4px 0 18px!important;border-color:#494478!important;background:radial-gradient(circle at 10% 50%,#7444ff3a,transparent 38%),linear-gradient(115deg,#17142f,#111c2e 72%)!important}
body.fjord-public .fjm-home>#fonctionnement{order:5!important}
body.fjord-public .fjm-home>#questions{order:6!important}
body.fjord-public.light .fjm-home>#services,body.fjord-public.light .fjm-home>#realisations{background:linear-gradient(135deg,#f4f2ff,#edfaff)!important;border-color:#dedaf3!important}
body.fjord-public.light .fjm-home>#atelier{background:linear-gradient(115deg,#ede9ff,#e5f8ff)!important;border-color:#d5cbf2!important}
body.fjord-public .fjm-home .fjm-offers{grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
body.fjord-public .fjm-home .fjm-offer{position:relative;overflow:hidden;min-height:210px;border-color:#353f61!important;background:linear-gradient(155deg,#1a2038,#101728)!important;transition:transform .2s,border-color .2s,box-shadow .2s}
body.fjord-public .fjm-home .fjm-offer:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#8b5cff,#35e1ff,#d8ff43)}
body.fjord-public .fjm-home .fjm-offer:hover{transform:translateY(-5px);border-color:#8b5cff!important;box-shadow:0 16px 36px #04050d,0 0 20px #8b5cff25!important}
body.fjord-public .fjm-home .fjm-offer h3{color:#f5f7ff!important}
body.fjord-public .fjm-home .fjm-offer p{color:#bac4dc!important}
body.fjord-public .fjm-home .fjm-offer a{color:#8beeff!important}
body.fjord-public .fjm-home .fjm-featured-track .fjm-project{border-color:#343e60!important;background:linear-gradient(160deg,#171e33,#0f1523)!important}
body.fjord-public .fjm-home .fjm-project-content span{color:#8beeff!important}
body.fjord-public .fjm-home .fjm-model-available,body.fjord-public .fjm-home .fjm-ready-count{color:#dbff60!important}
body.fjord-public .fjm-home .fjm-project-actions .fjm-project-quote{background:#d8ff43!important;border-color:#ecff9a!important;color:#11150a!important}
body.fjord-public .fjord-visitor-counter{border-color:#44416d!important;border-radius:14px!important;background:#15192b!important;color:#dbe1f3!important}
body.fjord-public .fjord-visitor-counter strong{color:#d8ff43!important}
body.fjord-public.light .fjord-visitor-counter{background:#fff!important;color:#373650!important}
body.fjord-public>footer{border-color:#303451!important;background:#080b15!important;color:#c0c6da!important}
body.fjord-public>footer a{color:#64eaff!important}
body.fjord-public.light>footer{border-color:#dedff0!important;background:#e9eaf5!important;color:#4d526b!important}
body.fjord-public.light>footer a{color:#176b96!important}
body.fjord-public .fjord-mobile-quote-cta{border-color:#f1ff9e!important;background:linear-gradient(105deg,#e1ff59,#b6ef27)!important;color:#101506!important;box-shadow:0 10px 28px #07090f99,0 0 22px #d8ff4355!important}
body.fjord-public :is(a,button,input,textarea,select):focus-visible{outline-color:#35e1ff!important}
@keyframes electric-breathe{0%,100%{box-shadow:0 28px 75px #03030caa,0 0 28px #6d48d422}50%{box-shadow:0 28px 78px #03030caa,0 0 46px #8b5cff44}}
@media(max-width:980px){body.fjord-public .fjm-home .fjm-offers{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){body.fjord-public .fjm-home>#services,body.fjord-public .fjm-home>#realisations{padding:16px;border-radius:21px}body.fjord-public .fjm-home .fjm-offers{grid-template-columns:1fr 1fr;gap:10px}body.fjord-public .fjm-home .fjm-offer{min-height:0;padding:15px}body.fjord-public .fjm-home>#atelier{border-radius:21px}body.fjord-public .fjm-home .fjm-hero{animation:none}}
@media(max-width:460px){body.fjord-public .fjm-home .fjm-offers{grid-template-columns:1fr}body.fjord-public .fjm-home .fjm-offer{min-height:0}body.fjord-public .fjm-home>#services,body.fjord-public .fjm-home>#realisations{padding:13px}}
@media(prefers-reduced-motion:reduce){body.fjord-public .fjm-home .fjm-hero{animation:none!important}body.fjord-public .fjm-home .fjm-offer{transition:none!important}}
/* Page-wide composition: storefront, catalogue, project detail and quote flow. */
body.fjord-public>main{display:flex;flex-direction:column;gap:clamp(20px,3vw,36px);width:min(100%,1480px)!important;max-width:1480px!important;margin-inline:auto!important;padding:clamp(22px,4vw,58px) clamp(16px,4vw,58px) clamp(84px,9vw,120px)!important}
body.fjord-public .site-header{position:sticky!important;top:0;min-height:76px;grid-template-columns:auto minmax(0,1fr) auto;gap:clamp(9px,1.5vw,22px);padding:9px clamp(14px,3vw,46px)!important}
body.fjord-public .site-header nav{justify-content:center;gap:3px;flex-wrap:nowrap}
body.fjord-public .site-header nav a{font-size:12px;padding:8px 9px}
body.fjord-public .fjm-home{display:flex;flex-direction:column;gap:clamp(18px,2.8vw,34px)}
body.fjord-public .fjm-home>.fjm-hero{order:0!important}
body.fjord-public .fjm-home>#services{order:1!important}
body.fjord-public .fjm-home>#realisations{order:2!important}
body.fjord-public .fjm-home>#atelier{order:3!important}
body.fjord-public .fjm-home>.fji-section{order:4!important}
body.fjord-public .fjm-home>#fonctionnement{order:5!important}
body.fjord-public .fjm-home>#questions{order:6!important}
body.fjord-public .fjm-home>.fjord-board{order:7!important}
body.fjord-public .fjm-home>.fjm-final{order:8!important}
body.fjord-public .fjm-home>#services,body.fjord-public .fjm-home>#realisations{scroll-margin-top:100px}
body.fjord-public .fjm-home .fjm-heading{max-width:880px;margin-bottom:clamp(16px,2.4vw,27px)}
body.fjord-public .fjm-home .fjm-heading h2{font-size:clamp(30px,4.4vw,52px);line-height:1.04}
body.fjord-public .fjm-home .fjm-offers{grid-template-columns:repeat(4,minmax(0,1fr))}
body.fjord-public .fjm-home .fjm-featured-track{gap:18px;padding:3px 3px 18px}
body.fjord-public .fjm-home .fjm-featured-track .fjm-project{flex-basis:calc((100% - 36px)/3);border-radius:22px!important}
body.fjord-public .fjm-home .fjm-featured-track .fjm-project img{height:auto;aspect-ratio:1.35;object-fit:cover}
body.fjord-public .fjm-home .fjm-final{display:flex;align-items:center;justify-content:space-between;gap:26px;margin-top:0!important;padding:clamp(22px,4vw,44px)!important;border-radius:28px!important;background:radial-gradient(ellipse at 90% 10%,#8b5cff55,transparent 40%),linear-gradient(120deg,#181633,#101d33)!important}
body.fjord-public .fjm-home .fjm-final h2{font-size:clamp(27px,3.6vw,42px)!important;color:#f5f7ff!important}
body.fjord-public .fjm-home .fjm-final p{display:block;color:#cbd3e8}
body.fjord-public.light .fjm-home .fjm-final{background:linear-gradient(120deg,#ebe8ff,#e5f8ff)!important}
body.fjord-public.light .fjm-home .fjm-final h2{color:#17172b!important}
body.fjord-public.light .fjm-home .fjm-final p{color:#555d78}
/* Catalogue becomes a filter bar followed by a four-column product wall. */
body.fjord-public main:has(#fjmGalleryItems) .fjm-section{width:100%;margin:0!important}
body.fjord-public main:has(#fjmGalleryItems) .fjm-heading{max-width:900px;margin:0 0 28px}
body.fjord-public main:has(#fjmGalleryItems) .fjm-heading h1{font-size:clamp(40px,6vw,76px);line-height:.98}
body.fjord-public .fjm-gallery-controls{display:grid;grid-template-columns:minmax(220px,2fr) minmax(170px,1fr) auto auto;gap:10px;align-items:center;margin:0 0 24px;padding:14px;border:1px solid #343b60;border-radius:20px;background:linear-gradient(130deg,#151a31,#101624)}
body.fjord-public .fjm-gallery-controls input{width:100%;max-width:none;min-width:0;min-height:48px;margin:0}
body.fjord-public .fjm-gallery-controls select{width:100%;max-width:none;min-height:48px;margin:0}
body.fjord-public .fjm-gallery-controls .fjm-filter{min-height:46px;border-radius:13px!important}
body.fjord-public .fjm-gallery-controls .fjm-gallery-count{grid-column:1/-1;color:#9da9c7;font-size:13px}
body.fjord-public.light .fjm-gallery-controls{background:linear-gradient(130deg,#f1efff,#effaff);border-color:#d9d9ee}
body.fjord-public .fjm-gallery{grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}
body.fjord-public .fjm-project{border-radius:22px!important}
body.fjord-public .fjm-project-image-link{display:block;overflow:hidden;background:#0b1020}
body.fjord-public .fjm-project img,body.fjord-public .fjm-project .fjm-project-noimage{height:auto;aspect-ratio:1.25;object-fit:cover}
body.fjord-public .fjm-project-content{display:flex;flex:1;flex-direction:column;align-items:flex-start;padding:18px}
body.fjord-public .fjm-project-content strong{font-size:18px;line-height:1.25}
body.fjord-public .fjm-project-actions{width:100%;margin-top:auto;padding-top:14px}
body.fjord-public .fjm-project-actions a{flex:1;min-height:44px;border-radius:12px!important;text-align:center}
body.fjord-public .fjm-gallery-empty{padding:clamp(20px,4vw,40px);border-radius:22px}
/* Project detail: breadcrumb and action band lead into an image gallery. */
body.fjord-public .gallery-detail{display:flex;flex-direction:column;gap:14px;max-width:1220px;margin:0 auto}
body.fjord-public .gallery-detail .fjord-breadcrumbs{display:flex;flex-wrap:wrap;align-items:center;gap:9px;width:100%;margin-bottom:8px;padding:12px 15px;border:1px solid #343b60;border-radius:14px;background:#111729}
body.fjord-public.light .gallery-detail .fjord-breadcrumbs{background:#fff;border-color:#dedff0}
body.fjord-public .gallery-detail h1{max-width:18ch;margin:5px 0;font-size:clamp(38px,6vw,70px);line-height:.99}
body.fjord-public .gallery-detail>.eyebrow{align-self:flex-start;padding:7px 11px;border:1px solid #524786;border-radius:999px;background:#201b3e;color:#a6efff;letter-spacing:.1em}
body.fjord-public .gallery-detail>.fjord-model-ready{margin:0;border-color:#668a35;background:#23321b;color:#e0ff64}
body.fjord-public .gallery-detail>p{max-width:78ch;margin:0}
body.fjord-public .fjord-gallery-detail-cta{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;margin:12px 0;padding:14px;border:1px solid #3a3d66;border-radius:20px;background:linear-gradient(120deg,#171a31,#111827)}
body.fjord-public .fjord-gallery-detail-cta>.btn,body.fjord-public .fjord-gallery-detail-cta>button{min-width:0;min-height:52px;border-radius:14px!important}
body.fjord-public .fjord-gallery-detail-cta>.secondary-btn,body.fjord-public .fjord-gallery-detail-cta>.fjord-share-project{background:#222641!important;border-color:#5f5b89!important;color:#eef0ff!important}
body.fjord-public.light .fjord-gallery-detail-cta{background:linear-gradient(120deg,#f0edff,#eafaff);border-color:#dbd9ef}
body.fjord-public.light .fjord-gallery-detail-cta>.secondary-btn,body.fjord-public.light .fjord-gallery-detail-cta>.fjord-share-project{background:#fff!important;color:#342b5c!important;border-color:#d1c9f0!important}
body.fjord-public .gallery-detail .fjord-gallery-linked{grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:10px}
body.fjord-public .fjord-gallery-linked-item{min-width:0;padding:10px;border:1px solid #343b60;border-radius:20px;background:#111729}
body.fjord-public.light .fjord-gallery-linked-item{background:#fff;border-color:#dedff0}
body.fjord-public .gallery-detail .gallery-photo-link img{height:auto;aspect-ratio:1.25;object-fit:cover;border-radius:14px}
body.fjord-public .fjord-gallery-linked-item>p{margin:10px 4px;font-size:13px}
body.fjord-public .fjord-gallery-linked-quote{display:flex;align-items:center;justify-content:center;min-height:44px;margin-top:10px;padding:9px 12px;border-radius:12px;background:#d8ff43;color:#101506!important;font-weight:850;text-align:center}
/* Quote page: clear introduction, guided start, then a calm two-column form. */
body.fjord-public main:has(.fjm-quote-form){max-width:1160px!important}
body.fjord-public main:has(.fjm-quote-form)>.eyebrow{align-self:flex-start;padding:8px 12px;border:1px solid #51437f;border-radius:99px;background:#1d1938;color:#97edff;font-weight:850}
body.fjord-public main:has(.fjm-quote-form)>h1{max-width:13ch;margin:0;font-size:clamp(42px,7vw,82px);line-height:.96}
body.fjord-public main:has(.fjm-quote-form)>.fjm-quote-helper{width:100%;max-width:none;margin:0;padding:22px 25px;border-color:#3d4770!important;border-radius:22px!important;background:linear-gradient(110deg,#171831,#112033)!important}
body.fjord-public main:has(.fjm-quote-form)>.fjm-quote-helper ul{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px 24px;margin-top:15px;padding-left:20px}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start{width:100%;max-width:none;margin:0}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start a{min-height:92px;border:1px solid #3e4670;border-radius:18px;background:linear-gradient(145deg,#171b33,#111827);box-shadow:0 10px 25px #03040b77}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start a:hover{border-color:#8b5cff;box-shadow:0 0 24px #8b5cff2a}
body.fjord-public.light main:has(.fjm-quote-form)>.fjm-quote-helper{background:linear-gradient(110deg,#f0edff,#eafaff)!important;border-color:#dbd9ef!important}
body.fjord-public.light main:has(.fjm-quote-form) .fjm-quote-start a{background:linear-gradient(145deg,#fff,#f4f3ff);border-color:#d9d9ee;color:#24213d!important}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 18px;width:100%;max-width:none;margin:0;padding:clamp(18px,3vw,34px);border:1px solid #3b4569!important;border-radius:25px!important;background:linear-gradient(145deg,#131a2b,#0f1522)!important}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label:nth-of-type(1),body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label:nth-of-type(2){grid-column:span 1}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label:nth-of-type(3),body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>.fjm-quote-options,body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>.fjord-brief,body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label:has(textarea),body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>.fjm-files,body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>.fjm-form-submit,body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>.fjm-quote-note{grid-column:1/-1}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label{margin:0 0 5px;padding:14px;border:1px solid #303a59;border-radius:15px;background:#111827}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label input,body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label textarea{margin:8px 0 0}
body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form .fjm-form-submit{margin-top:10px;min-height:58px;font-size:16px}
body.fjord-public.light main:has(.fjm-quote-form) .fjm-quote-form{background:linear-gradient(145deg,#fff,#f5f4ff)!important;border-color:#dedff0!important}
body.fjord-public.light main:has(.fjm-quote-form) .fjm-quote-form>label{background:#fff;border-color:#e0e1ef}
/* Tracking and contact pages get a focused, centered task panel. */
body.fjord-public .tracking-panel{display:flex;flex-direction:column;gap:14px;width:100%;max-width:820px;margin:0 auto;padding:clamp(22px,4vw,42px);border:1px solid #343b60;border-radius:28px;background:radial-gradient(ellipse at 90% 0%,#8b5cff31,transparent 36%),linear-gradient(145deg,#141a2d,#101625);box-shadow:0 20px 50px #03040b88}
body.fjord-public .tracking-panel .eyebrow{color:#8beeff;letter-spacing:.14em}
body.fjord-public .tracking-panel h1{font-size:clamp(36px,5vw,58px);line-height:1}
body.fjord-public .tracking-panel form{width:100%;max-width:none;margin:8px 0 0;padding:20px;border:1px solid #343b60;border-radius:20px;background:#0e1422}
body.fjord-public .tracking-panel form button{width:100%;margin-top:6px}
body.fjord-public .tracking-result{padding:22px!important;border-radius:20px!important}
body.fjord-public .tracking-billboard{border-radius:26px!important;background:radial-gradient(ellipse at 90% 0%,#8b5cff44,transparent 42%),linear-gradient(120deg,#181731,#102033)!important}
body.fjord-public.light .tracking-panel,body.fjord-public.light .tracking-panel form{background:linear-gradient(145deg,#f1efff,#effaff);border-color:#dedff0}
body.fjord-public.light .tracking-panel form{background:#fff}
body.fjord-public.light .tracking-billboard{background:linear-gradient(120deg,#ece9ff,#e8faff)!important}
body.fjord-public .contact-section{width:100%;max-width:1000px;margin:20px auto 0;padding:clamp(20px,4vw,40px);border-radius:24px!important}
body.fjord-public .contact-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
body.fjord-public .contact-actions a{justify-content:flex-start;min-height:56px;border-radius:14px;background:#171d32;color:#eef0ff}
body.fjord-public.light .contact-actions a{background:#fff;color:#342b5c;border-color:#dedff0}
body.fjord-public .fjord-thanks{max-width:850px;margin:0 auto;padding:clamp(22px,5vw,52px);border:1px solid #454078;border-radius:28px;background:radial-gradient(ellipse at 100% 0%,#8b5cff44,transparent 40%),linear-gradient(145deg,#17162e,#101b2b)}
body.fjord-public .fjord-thanks-symbol{color:#d8ff43;text-shadow:0 0 25px #d8ff4366}
/* Responsive layouts keep the same hierarchy without horizontal scrolling. */
@media(max-width:1050px){body.fjord-public .fjm-gallery{grid-template-columns:repeat(3,minmax(0,1fr))}body.fjord-public .fjm-home .fjm-featured-track .fjm-project{flex-basis:calc((100% - 18px)/2)}body.fjord-public .fjord-gallery-detail-cta{grid-template-columns:1fr 1fr}body.fjord-public .fjord-gallery-detail-cta>.btn:first-child{grid-column:1/-1}}
@media(max-width:760px){body.fjord-public>main{gap:20px;padding:20px 14px 95px!important}body.fjord-public .site-header{grid-template-columns:minmax(0,1fr) auto!important;padding:8px 12px!important}body.fjord-public .site-header nav{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px 0}body.fjord-public .site-header nav a{justify-content:center;min-height:44px;white-space:normal;text-align:center}body.fjord-public .site-header .pref-controls{grid-column:1/-1;grid-row:3;justify-content:flex-end}body.fjord-public .fjm-gallery-controls{grid-template-columns:1fr 1fr;padding:10px}body.fjord-public .fjm-gallery-controls input,body.fjord-public .fjm-gallery-controls select{grid-column:1/-1}body.fjord-public .fjm-gallery{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}body.fjord-public .fjm-project-content{padding:13px}body.fjord-public .fjm-project-actions{display:grid;grid-template-columns:1fr}body.fjord-public .gallery-detail .fjord-gallery-linked{grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}body.fjord-public .fjord-gallery-detail-cta{grid-template-columns:1fr}body.fjord-public .fjord-gallery-detail-cta>.btn:first-child{grid-column:1}body.fjord-public main:has(.fjm-quote-form)>.fjm-quote-helper ul{grid-template-columns:1fr}body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form{grid-template-columns:1fr}body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>*{grid-column:1/-1!important}body.fjord-public .contact-actions{grid-template-columns:1fr}}
@media(max-width:460px){body.fjord-public .fjm-gallery{grid-template-columns:1fr}body.fjord-public .gallery-detail .fjord-gallery-linked{grid-template-columns:1fr}body.fjord-public .fjm-home .fjm-featured-track .fjm-project{flex-basis:100%}body.fjord-public .fjm-home .fjm-final{display:flex!important;flex-direction:column!important;align-items:stretch!important}body.fjord-public .fjm-home .fjm-final .btn{width:100%}body.fjord-public .tracking-panel{padding:18px}body.fjord-public .gallery-detail h1{font-size:clamp(32px,10vw,48px)}}
@media(prefers-reduced-motion:reduce){body.fjord-public *{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
/* Mobile polish: compact header, consistent card rhythm, no cramped controls. */
@media(max-width:760px){
 body.fjord-public>main{padding:16px 12px 92px!important;gap:18px}
 body.fjord-public .site-header{grid-template-columns:minmax(0,1fr) auto!important;grid-template-rows:auto auto auto;gap:5px 8px;padding:8px 11px!important}
 body.fjord-public .site-header .brand{grid-column:1;grid-row:1;grid-template-columns:39px minmax(0,1fr);column-gap:8px;font-size:13px;line-height:1.05}
 body.fjord-public .site-header .brand img{width:38px!important;height:38px!important;border-radius:10px}
 body.fjord-public .site-header .brand-main,body.fjord-public .site-header .brand-blue{white-space:nowrap}
 body.fjord-public .site-header .fjord-brand-tagline{margin-top:2px;font-size:7px;letter-spacing:.1em}
 body.fjord-public .site-nav-toggle{grid-column:2;grid-row:1;min-height:40px;padding:8px 11px}
 body.fjord-public .site-header .pref-controls{grid-column:1/-1;grid-row:2;width:100%;justify-content:flex-end;gap:6px}
 body.fjord-public .site-header .pref-controls select{min-height:36px;max-width:125px;padding:5px 8px;font-size:11px}
 body.fjord-public .site-header nav{grid-column:1/-1;grid-row:3;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:7px 0 2px}
 body.fjord-public .site-header nav a{min-height:42px;padding:8px 6px;font-size:12px}
 body.fjord-public .fjm-home{gap:16px}
 body.fjord-public .fjm-home .fjm-hero{padding:17px 15px!important;border-radius:20px!important}
 body.fjord-public .fjm-home .fjm-hero h1{font-size:clamp(37px,10vw,48px)!important;line-height:.99}
 body.fjord-public .fjm-home .fjm-hero-lead{font-size:15px;line-height:1.5}
 body.fjord-public .fjm-home .fjm-hero-photo-grid,body.fjord-public .fjm-home .fjm-hero-photo-grid>a,body.fjord-public .fjm-home .fjm-hero-photo-grid img{height:160px!important;min-height:160px!important;grid-template-rows:160px!important;grid-auto-rows:160px!important}
 body.fjord-public .fjm-home>#services,body.fjord-public .fjm-home>#realisations{margin:0!important;padding:15px;border-radius:20px}
 body.fjord-public .fjm-home .fjm-heading{margin-bottom:14px}
 body.fjord-public .fjm-home .fjm-heading h2{font-size:clamp(27px,7vw,36px);line-height:1.08}
 body.fjord-public .fjm-home .fjm-offers{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
 body.fjord-public .fjm-home .fjm-offer{min-width:0;min-height:0;padding:13px;border-radius:16px!important}
 body.fjord-public .fjm-home .fjm-offer h3{font-size:15px;line-height:1.2}
 body.fjord-public .fjm-home .fjm-offer p{font-size:12px;line-height:1.4}
 body.fjord-public .fjm-home .fjm-offer a{font-size:12px}
 body.fjord-public .fjm-gallery-controls{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}
 body.fjord-public .fjm-gallery-controls input,body.fjord-public .fjm-gallery-controls select{grid-column:1/-1;min-width:0}
 body.fjord-public .fjm-gallery-controls .fjm-filter{min-width:0;min-height:42px;padding:8px 6px;font-size:12px}
 body.fjord-public .fjm-gallery{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
 body.fjord-public .fjm-project{border-radius:17px!important}
 body.fjord-public .fjm-project img,body.fjord-public .fjm-project .fjm-project-noimage{aspect-ratio:1.05}
 body.fjord-public .fjm-project-content{padding:11px;gap:3px}
 body.fjord-public .fjm-project-content span{font-size:9px;letter-spacing:.06em}
 body.fjord-public .fjm-project-content strong{margin:4px 0;font-size:14px;line-height:1.2}
 body.fjord-public .fjm-project-content small,body.fjord-public .fjm-project-content .fjm-model-available{font-size:11px!important}
 body.fjord-public .fjm-project-actions{display:grid;grid-template-columns:1fr;gap:6px;margin-top:7px;padding-top:4px}
 body.fjord-public .fjm-project-actions a{min-height:40px;padding:7px 8px;font-size:11px}
 body.fjord-public main:has(.fjm-quote-form)>h1{font-size:clamp(38px,10vw,54px);line-height:1}
 body.fjord-public main:has(.fjm-quote-form)>.fjm-quote-helper{padding:16px;border-radius:17px!important}
 body.fjord-public main:has(.fjm-quote-form)>.fjm-quote-helper ul{gap:7px;margin:10px 0 0;font-size:13px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start{gap:7px;margin:0}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start a{min-height:58px;padding:10px 12px;border-radius:14px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start a strong{font-size:13px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-start a span{font-size:11px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form{gap:8px;padding:13px;border-radius:18px!important}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form>label{padding:11px;border-radius:13px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form :is(input,textarea,select){min-height:46px;font-size:16px}
 body.fjord-public main:has(.fjm-quote-form) .fjm-quote-form textarea{min-height:120px}
 body.fjord-public .tracking-panel{padding:18px;border-radius:20px}
 body.fjord-public .contact-section{padding:17px;border-radius:19px!important}
 body.fjord-public .contact-actions{grid-template-columns:1fr;gap:8px}
 body.fjord-public .contact-actions a{min-height:48px;padding:10px 12px}
 body.fjord-public>footer{gap:10px;padding:20px 14px}
}
@media(max-width:380px){body.fjord-public .fjm-home .fjm-offers,body.fjord-public .fjm-gallery{grid-template-columns:1fr}body.fjord-public .fjm-home .fjm-offer{padding:14px}body.fjord-public .fjm-project img,body.fjord-public .fjm-project .fjm-project-noimage{aspect-ratio:1.35}}
/* Featured photographs are actual printed parts, large enough to register immediately. */
.fjm-home .fjm-hero-proof{padding:15px!important}
.fjm-home .fjm-hero-photo-grid{position:relative;display:block!important;height:clamp(300px,34vw,430px)!important;overflow:hidden;border-radius:20px;background:#08111b}
.fjm-home .fjm-hero-photo-grid>a{position:absolute;display:block!important;overflow:hidden;border:1px solid #ffffff55;border-radius:18px;background:#101923;box-shadow:0 18px 42px #0008}
.fjm-home .fjm-hero-photo-grid>a:first-child{inset:0;width:100%;height:100%!important;min-height:0!important}
.fjm-home .fjm-hero-photo-grid>a:nth-child(2){right:14px;bottom:14px;width:38%;height:43%!important;min-height:0!important;border:3px solid #f6fdff;box-shadow:0 12px 30px #000a}
.fjm-home .fjm-hero-photo-grid img{display:block;width:100%!important;height:100%!important;min-height:0!important;max-height:none!important;object-fit:cover;border-radius:inherit!important;filter:saturate(1.12) contrast(1.04)}
.fjm-home .fjm-real-photo-label{position:absolute;left:12px;bottom:12px;z-index:1;max-width:calc(100% - 24px);padding:9px 12px;border:1px solid #dcff4f;border-radius:999px;background:#10170ee8;color:#f4ffc2;font-size:11px;font-weight:950;letter-spacing:.06em;line-height:1.2;box-shadow:0 6px 20px #0008}
.fjm-home .fjm-hero-photo-grid>a:nth-child(2) .fjm-real-photo-label{left:7px;bottom:7px;padding:6px 8px;font-size:9px}
.fjm-filter-real[aria-pressed=true]{background:#d8ff43;color:#14200a;border-color:#efff9b;box-shadow:0 0 22px #d8ff4355}
body.fjord-public .fjm-gallery-controls .fjm-category-filters{display:contents}
body.fjord-public .fjm-gallery-controls .fjm-category-filters .fjm-filter{background:#112b40;color:#dceaf3;border-color:#39556a}
body.fjord-public .fjm-gallery-controls .fjm-category-filters .fjm-filter[aria-pressed=true]{background:#d8ff43;color:#14200a;border-color:#efff9b}
body.fjord-public .fjm-gallery-controls:has(#fjmGalleryReal[aria-pressed="true"]) .fjm-category-filters{display:none!important}
body.fjord-public.fjm-real-gallery-only .fjm-gallery-controls .fjm-category-filters{display:none!important}
.fjm-home .fjm-proof-eyebrow{margin-top:13px!important}
.fjm-home .fjm-hero-proof h2{margin-bottom:4px!important}
body.light .fjm-home .fjm-hero-photo-grid{background:#dbe6ee}
@media(max-width:760px){.fjm-home .fjm-hero-photo-grid{height:clamp(240px,61vw,330px)!important}.fjm-home .fjm-hero-photo-grid>a:nth-child(2){right:10px;bottom:10px;width:40%;height:42%!important}.fjm-home .fjm-real-photo-label{left:9px;bottom:9px;padding:8px 10px;font-size:10px}}
@media(max-width:640px){.fjm-home .fjm-hero{grid-template-columns:minmax(0,1fr)!important}.fjm-home .fjm-hero-proof{grid-row:1!important;margin:0 0 15px!important;padding:8px!important}.fjm-home .fjm-hero>div>.fjm-kicker{grid-row:2!important}.fjm-home .fjm-hero>div>h1{grid-row:3!important}.fjm-home .fjm-hero>div>.fjm-hero-lead{grid-row:4!important}.fjm-home .fjm-hero>div>.fjm-hero-actions{grid-row:5!important}.fjm-home .fjm-hero>div>.fjm-hero-sub{grid-row:6!important}.fjm-home .fjm-hero-photo-grid{height:clamp(235px,66vw,290px)!important}.fjm-home .fjm-proof-eyebrow,.fjm-home .fjm-hero-proof h2,.fjm-home .fjm-hero-proof>p:last-child{display:none!important}}
@media(max-width:380px){.fjm-home .fjm-hero-photo-grid{height:225px!important}.fjm-home .fjm-hero-photo-grid>a:nth-child(2){width:41%;height:40%!important}}
/* Hero v2: studio clair, cobalt électrique et corail pour un impact mobile immédiat. */
body.fjord-public main .fjm-home>.fjm-hero{position:relative;isolation:isolate;overflow:hidden;background:radial-gradient(circle at 8% 96%,#ff735329,transparent 32%),radial-gradient(circle at 91% 7%,#3b6cff2b,transparent 35%),linear-gradient(132deg,#fffdf7 0%,#f4f7ff 57%,#fff0e8 100%)!important;border:2px solid #ffffff;border-radius:30px;box-shadow:0 30px 90px #03144038;color:#101a30}
body.fjord-public main .fjm-home>.fjm-hero:before{content:"";position:absolute;z-index:-1;right:42%;bottom:-210px;width:430px;height:430px;border:1px solid #355fff20;border-radius:50%;box-shadow:0 0 0 28px #355fff08,0 0 0 58px #ff573508}
body.fjord-public main .fjm-home .fjm-hero>div{position:relative;z-index:1}
body.fjord-public main .fjm-home .fjm-hero .fjm-kicker{display:inline-flex;align-items:center;min-height:31px;padding:7px 12px;border-radius:999px;background:#1747e8;color:#fff;font-size:10px;letter-spacing:.13em;box-shadow:0 7px 20px #1747e82b}
body.fjord-public main .fjm-home .fjm-hero>div>.fjm-kicker{gap:7px;min-height:36px;padding:8px 14px;border:1px solid #ffb5a5;background:linear-gradient(105deg,#173fd5 0%,#087fc8 68%,#e9473c 100%);box-shadow:0 10px 26px #1747e84f,0 0 24px #f04f3d35;font-size:11px;font-weight:950;letter-spacing:.1em;line-height:1.3}
/* Photo hero : donner la première place à la sculpture Bouvier-Bernois, une réalisation unique et réelle. */
body.fjord-public main .fjm-home .fjm-hero-photo-grid{border:3px solid #f9fbff;box-shadow:0 0 0 2px #ef503f,0 0 34px #1747e858,0 20px 52px #08143170}
body.fjord-public main .fjm-home .fjm-hero-photo-grid img{filter:saturate(1.18) contrast(1.08) brightness(1.06)}
body.fjord-public main .fjm-home .fjm-hero-photo-grid>a:first-child img{object-position:center 48%}
body.fjord-public main .fjm-home .fjm-hero-showcase{position:relative;border:3px solid transparent!important;border-radius:26px!important;background:linear-gradient(135deg,#f8fbff,#f8fbff) padding-box,linear-gradient(140deg,#36dcff,#3857ff 46%,#ff624d) border-box!important;box-shadow:0 0 0 1px #b5cfff66,0 24px 58px #06133480!important}
body.fjord-public main .fjm-home .fjm-hero-showcase>a:first-child{border:0!important;border-radius:22px!important}
body.fjord-public main .fjm-home .fjm-hero-showcase>a:first-child:after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;background:linear-gradient(180deg,#07182d12 28%,transparent 48%,#07182da6 100%)}
body.fjord-public main .fjm-home .fjm-hero-feature-tag{position:absolute;z-index:2;top:16px;left:16px;padding:10px 14px;border:1px solid #fff9;border-radius:999px;background:linear-gradient(105deg,#163fd9ed,#067fc7ed 62%,#e94d43ed);color:#fff;font-size:11px;font-weight:950;letter-spacing:.08em;box-shadow:0 9px 24px #08133488}
body.fjord-public main .fjm-home .fjm-hero-showcase .fjm-real-photo-label{border:1px solid #ffffffd4;background:#08152fe8;color:#fff;box-shadow:0 7px 22px #03081780}
body.fjord-public main .fjm-home .fjm-hero-showcase>a:nth-child(2){right:16px;bottom:16px;width:34%;height:40%!important;border:3px solid #fff!important;border-radius:18px!important;box-shadow:0 14px 34px #03081799}
body.fjord-public main .fjm-home .fjm-hero-showcase>a:nth-child(2) .fjm-real-photo-label{left:7px;bottom:7px;padding:6px 8px;font-size:9px}
@media(max-width:760px){body.fjord-public main .fjm-home .fjm-hero-showcase{height:clamp(330px,82vw,470px)!important;border-radius:25px!important}body.fjord-public main .fjm-home .fjm-hero-feature-tag{top:12px;left:12px;padding:9px 11px;font-size:10px}body.fjord-public main .fjm-home .fjm-hero-showcase>a:nth-child(2){right:12px;bottom:12px;width:38%;height:37%!important}}
@media(max-width:460px){body.fjord-public main .fjm-home .fjm-hero-showcase{height:clamp(290px,83vw,360px)!important}body.fjord-public main .fjm-home .fjm-hero-showcase>a:nth-child(2){width:39%;height:36%!important}body.fjord-public main .fjm-home .fjm-hero-feature-tag{font-size:9px;letter-spacing:.05em}}
@media(max-width:760px){body.fjord-public main .fjm-home .fjm-hero-photo-grid{height:clamp(285px,72vw,390px)!important}}
@media(max-width:460px){body.fjord-public main .fjm-home .fjm-hero-photo-grid{height:clamp(255px,74vw,320px)!important}}
body.fjord-public main .fjm-home .fjm-hero h1{color:#101a30!important;max-width:730px;font-size:clamp(42px,6.4vw,82px)!important;line-height:.99!important;letter-spacing:-.065em!important}
body.fjord-public main .fjm-home .fjm-hero .fjm-accent{background:linear-gradient(95deg,#1847eb 4%,#077fc7 48%,#f04f3d 100%);-webkit-background-clip:text;background-clip:text;color:transparent!important;-webkit-text-fill-color:transparent!important}
body.fjord-public main .fjm-home .fjm-hero .fjm-hero-lead{max-width:610px;color:#43516a!important;font-size:clamp(16px,1.75vw,20px);line-height:1.55}
body.fjord-public main .fjm-home .fjm-hero-actions{gap:12px;margin-top:23px}
body.fjord-public main .fjm-home .fjm-hero-actions .btn{min-height:54px;padding:14px 22px;border-radius:14px!important;font-weight:900;box-shadow:0 11px 24px #142d6240;transition:transform .18s,box-shadow .18s}
body.fjord-public main .fjm-home .fjm-hero-actions .btn:first-child{background:linear-gradient(105deg,#1747e8,#087fc8)!important;border:1px solid #1747e8!important;color:#fff!important}
body.fjord-public main .fjm-home .fjm-hero-actions .btn:last-child{background:#fff!important;border:1px solid #ff6b50!important;color:#bd382a!important;box-shadow:0 8px 20px #f04f3d18}
body.fjord-public main .fjm-home .fjm-hero-actions .btn:hover{transform:translateY(-3px);box-shadow:0 16px 29px #1747e83c}
body.fjord-public main .fjm-home .fjm-hero .fjm-hero-sub{color:#52617a!important;font-size:13px;font-weight:650}
body.fjord-public main .fjm-home .fjm-points{display:flex!important;gap:8px;margin-top:16px}
body.fjord-public main .fjm-home .fjm-points li{border:1px solid #ccd8f4;border-radius:11px;background:#ffffffc9;color:#263b72;font-size:11px;box-shadow:0 5px 15px #15254c0d}
body.fjord-public main .fjm-home .fjm-hero-proof{position:relative;z-index:1;padding:14px!important;border:1px solid #516da8!important;border-radius:25px!important;background:linear-gradient(155deg,#0b1730,#14274a)!important;box-shadow:0 24px 55px #101d3f48!important;color:#f8fbff}
body.fjord-public main .fjm-home .fjm-hero-photo-grid{border:4px solid #f5f7ff;border-radius:19px;background:#081329;box-shadow:0 13px 32px #02081780}
body.fjord-public main .fjm-home .fjm-hero-photo-grid>a{border:1px solid #ffffff8a;background:#0c1423}
body.fjord-public main .fjm-home .fjm-real-photo-label{border-color:#ff684f;background:#101b35ed;color:#fff;font-size:10px;letter-spacing:.09em}
body.fjord-public main .fjm-home .fjm-proof-eyebrow{color:#a8c4ff!important}
body.fjord-public main .fjm-home .fjm-hero-proof h2{color:#fff!important;font-size:clamp(23px,2.4vw,31px)!important;letter-spacing:-.035em}
body.fjord-public main .fjm-home .fjm-hero-proof>p:last-child{color:#d7e2f8!important;font-size:15px;line-height:1.55}
body.fjord-public main .fjm-home>#atelier{position:relative;isolation:isolate;overflow:hidden;padding:clamp(20px,3vw,30px)!important;border:1px solid #8eafff!important;border-radius:24px!important;background:radial-gradient(circle at 0% 50%,#ff745444,transparent 27%),linear-gradient(118deg,#173fd5,#126fc9 58%,#14274e)!important;box-shadow:0 24px 52px #1747e83b!important;color:#fff}
body.fjord-public main .fjm-home>#atelier:after{content:"";position:absolute;z-index:-1;right:-105px;top:-150px;width:310px;height:310px;border:1px solid #ffffff28;border-radius:50%;box-shadow:0 0 0 24px #ffffff0c,0 0 0 50px #ff745411}
body.fjord-public main .fjm-home .fjm-atelier-mark{border:1px solid #ffffff9c;border-radius:20px;background:linear-gradient(145deg,#a0f3ff,#48bfea 54%,#2c65ef);color:#082751;font-size:35px;box-shadow:0 12px 30px #051a4455,0 0 32px #86eaff55}
body.fjord-public main .fjm-home .fjm-atelier-copy .fjm-kicker{color:#ffe1d7!important}
body.fjord-public main .fjm-home .fjm-atelier-copy h2{color:#fff!important;font-size:clamp(22px,2.8vw,32px);letter-spacing:-.04em}
body.fjord-public main .fjm-home .fjm-atelier-copy p{color:#e2ecff!important;font-size:15px;max-width:70ch}
body.fjord-public main .fjm-home .fjm-atelier-actions .btn{min-height:51px;padding:13px 20px;background:#fff!important;border:1px solid #fff!important;border-radius:13px!important;color:#1747c8!important;box-shadow:0 12px 25px #07184245!important;font-weight:950}
body.fjord-public main .fjm-home .fjm-atelier-actions .btn:hover{transform:translateY(-2px);box-shadow:0 16px 30px #07184266!important}
body.fjord-public main .fjm-home .fjm-atelier-secondary{color:#fff!important;font-weight:850;text-decoration-color:#ffb7a7;text-underline-offset:4px}
body.fjord-public main .fjm-home .fjm-atelier-note{border:1px solid #ffffffc9;border-radius:15px;background:#f8fbff;color:#14264c;box-shadow:0 12px 28px #07184233}
body.fjord-public main .fjm-home .fjm-atelier-note span{color:#1747c8}
body.fjord-public main .fjm-home .fjm-atelier-copy h2{max-width:760px}
body.fjord-public main .fjm-home .fjm-atelier-copy p{max-width:72ch}
body.fjord-public main .fjm-home .fjm-atelier-features{display:flex;flex-wrap:wrap;gap:7px;margin:13px 0 0;padding:0;list-style:none}
body.fjord-public main .fjm-home .fjm-atelier-features li{padding:6px 9px;border:1px solid #ffffff70;border-radius:999px;background:#081e4740;color:#f5f8ff;font-size:11px;font-weight:800;line-height:1.2}
body.fjord-public main .fjm-home .fjm-atelier-note strong{font-size:13px}
body.fjord-public main .fjm-home .fjm-atelier-note span{font-size:12px}
@media(max-width:760px){body.fjord-public main .fjm-home .fjm-atelier-features{grid-column:1/-1;margin-top:0}body.fjord-public main .fjm-home .fjm-atelier-note{grid-column:1/-1;width:fit-content;max-width:100%;flex-wrap:wrap}body.fjord-public main .fjm-home .fjm-atelier-copy{grid-column:2}body.fjord-public main .fjm-home .fjm-atelier-actions{grid-column:2}}
@media(max-width:460px){body.fjord-public main .fjm-home .fjm-atelier-copy,body.fjord-public main .fjm-home .fjm-atelier-actions,body.fjord-public main .fjm-home .fjm-atelier-features{grid-column:1}body.fjord-public main .fjm-home .fjm-atelier-note{grid-column:1}}
@media(max-width:760px){body.fjord-public main .fjm-home>.fjm-hero{padding:clamp(14px,4vw,24px)!important;border-radius:22px}body.fjord-public main .fjm-home .fjm-hero-proof{padding:9px!important;border-radius:18px!important}body.fjord-public main .fjm-home .fjm-hero h1{font-size:clamp(39px,10.5vw,58px)!important;line-height:1.02!important}body.fjord-public main .fjm-home .fjm-points{gap:6px}body.fjord-public main .fjm-home .fjm-points li{padding:7px 9px;font-size:10px}}
@media(max-width:420px){body.fjord-public main .fjm-home .fjm-hero-actions .btn{width:100%;min-height:50px}body.fjord-public main .fjm-home .fjm-hero .fjm-hero-sub{font-size:12px}}
</style>"""

MARKETING_HOME_START = """<div class="fjm-home">
<section class="fjm-hero" aria-labelledby="fjm-hero-title">
 <div><span class="fjm-kicker" data-fjm-en="⚡ YOUR IDEA TAKES SHAPE HERE · SAGUENAY">⚡ VOTRE IDÉE PREND FORME ICI · SAGUENAY</span>
 <h1 id="fjm-hero-title"><span data-fjm-en="Your idea.">Une idée.</span> <span class="fjm-accent" data-fjm-en="A part made for you.">Une pièce créée pour vous.</span></h1>
 <p class="fjm-hero-lead" data-fjm-en="A replacement part, a custom accessory or a one-of-a-kind gift. Tell us what you need and we’ll bring it to life here in Saguenay.">Une pièce introuvable? Un cadeau unique? Un projet en tête? Envoyez votre idée, une photo ou votre fichier 3D : nous préparons une soumission adaptée à votre besoin, ici au Saguenay.</p>
 <div class="fjm-hero-actions"><a class="btn" href="/soumission" data-fjm-en="Get my free quote">Obtenir ma soumission gratuite</a><a class="btn fjm-outline" href="/galerie?prets=1" data-fjm-en="Explore ready-to-print pieces">Découvrir les créations</a></div>
 <p class="fjm-hero-sub" data-fjm-en="No 3D file needed · Free quote · No obligation">Pas besoin de fichier 3D · Soumission gratuite · Sans engagement</p>
 <ul class="fjm-points"><li data-fjm-en="⚡ Custom-made parts">⚡ Pièce faite pour vous</li><li data-fjm-en="📍 Made in Saguenay">📍 Fabriqué au Saguenay</li><li data-fjm-en="✓ Free quote">✓ Soumission gratuite</li></ul>
 </div>
 <aside class="fjord-hero-studio" aria-label="Votre prochain projet prend forme">
  <div class="fjord-hero-orbit" aria-hidden="true"><span class="fjord-orbit-ring fjord-ring-one"></span><span class="fjord-orbit-ring fjord-ring-two"></span><span class="fjord-orbit-core">3D</span><span class="fjord-orbit-spark fjord-spark-a">✦</span><span class="fjord-orbit-spark fjord-spark-b">✧</span></div>
  <div class="fjord-studio-content">
   <span class="fjord-studio-eyebrow" data-fjm-en="FROM IDEA TO REALITY">DE L'IDÉE À LA RÉALITÉ</span>
   <h2 data-fjm-en="Your next great idea starts here.">Votre prochaine création commence ici.</h2>
   <p data-fjm-en="Bring a photo, a sketch or a 3D file. We help turn it into a real part.">Une photo, un croquis ou un fichier 3D : transformons votre projet en pièce réelle.</p>
   <a class="fjord-studio-link" href="/atelier-3d" data-fjm-en="Explore the 3D workshop →">Explorer l'Atelier 3D →</a>
  </div>
 </aside>
</section>
<section class="fjord-paths" aria-labelledby="fjord-paths-title">
 <div class="fjord-paths-intro"><span class="fjm-kicker" data-fjm-en="YOUR PROJECT, YOUR WAY">VOTRE PROJET, VOTRE FAÇON</span><h2 id="fjord-paths-title" data-fjm-en="What would you like to create?">On commence par quoi?</h2><p data-fjm-en="With a file or just an idea, there is a simple way to get started.">Que vous ayez un fichier ou simplement une idée, on a une solution pour vous.</p></div>
 <div class="fjord-paths-grid">
  <a class="fjord-path-card" href="/atelier-3d"><span aria-hidden="true">⬡</span><strong data-fjm-en="I already have a 3D file">J'ai déjà mon fichier 3D</strong><small data-fjm-en="Open the 3D workshop and import your STL or 3MF.">Ouvrir l'Atelier 3D et importer mon STL ou 3MF.</small><b data-fjm-en="Open the workshop →">Ouvrir l'atelier →</b></a>
  <a class="fjord-path-card" href="/soumission"><span aria-hidden="true">✦</span><strong data-fjm-en="Create my custom part">Créer ma pièce sur mesure</strong><small data-fjm-en="Describe your idea or send a photo to request a quote.">Décrire mon idée ou envoyer une photo pour obtenir un prix.</small><b data-fjm-en="Request my quote →">Demander mon prix →</b></a>
  <a class="fjord-path-card" href="/galerie?prets=1"><span aria-hidden="true">◈</span><strong data-fjm-en="Find a ready-to-print creation">Choisir une création existante</strong><small data-fjm-en="Browse projects and find a piece you like.">Parcourir les réalisations et choisir une pièce.</small><b data-fjm-en="Explore the gallery →">Voir les créations →</b></a>
 </div>
</section>
<section class="fjm-atelier" id="atelier" aria-labelledby="fjm-atelier-title">
 <div class="fjm-atelier-mark" aria-hidden="true">🧊</div>
 <div class="fjm-atelier-copy">
  <span class="fjm-kicker" data-fjm-en="CREATE YOUR PART RIGHT HERE · NO CAD SOFTWARE NEEDED">CRÉEZ VOTRE PIÈCE ICI · SANS LOGICIEL DE CAO</span>
  <h2 id="fjm-atelier-title" data-fjm-en="Imagine it. Build it in 3D. Make it yours.">Imaginez-la. Créez-la en 3D. À votre façon.</h2>
  <p data-fjm-en="Build a custom part right in your browser with 40 customizable 3D generators, or import an STL/3MF. Explore mechanical parts, useful accessories, reliefs and more before requesting a quote.">Créez une pièce sur mesure directement dans votre navigateur avec 40 générateurs 3D personnalisables, ou importez un STL/3MF. Explorez les pièces mécaniques, accessoires pratiques, reliefs et plus encore avant de demander une soumission.</p>
  <ul class="fjm-atelier-features" aria-label="Outils de création disponibles"><li data-fjm-en="⚙ Mechanical parts">⚙ Pièces mécaniques</li><li data-fjm-en="🧩 Custom accessories">🧩 Accessoires sur mesure</li><li data-fjm-en="📷 Photo to 3D relief">📷 Photo en relief 3D</li><li data-fjm-en="▦ Personalized QR codes">▦ Codes QR personnalisés</li></ul>
  <div class="fjm-atelier-actions"><a class="btn" href="/atelier-3d" data-fjm-en="✨ Create my part in 3D">✨ Créer ma pièce en 3D</a><a class="fjm-atelier-secondary" href="/soumission" data-fjm-en="I’d like help with my idea">Je veux être accompagné</a></div>
 </div>
 <div class="fjm-atelier-note"><strong data-fjm-en="No model file? No problem.">Pas de fichier 3D? Aucun problème.</strong><span data-fjm-en="Create online · STL · 3MF">Création en ligne · STL · 3MF</span></div>
</section>
<section class="fjm-section" id="services" aria-labelledby="fjm-services-title">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="What we make">CE QU’ON FABRIQUE</span><h2 id="fjm-services-title" data-fjm-en="Practical parts, prototypes and one-of-a-kind creations">Pièces utiles, prototypes et créations uniques</h2><p data-fjm-en="Tell us what the part needs to do. We will help choose a practical model, material and finish for your project.">Expliquez-nous à quoi doit servir la pièce. On vous aidera à choisir un modèle, un matériau et une finition adaptés à votre projet.</p></div>
 <div class="fjm-offers">
  <article class="fjm-offer"><span class="fjm-offer-icon" aria-hidden="true">⚙</span><h3 data-fjm-en="Replacement parts">Pièces de remplacement</h3><p data-fjm-en="A broken clip, cover, spacer or bracket? Share a photo and the approximate measurements.">Clip, couvercle, entretoise ou support brisé? Envoyez une photo et des dimensions approximatives.</p><a href="/soumission" data-fjm-en="Describe the part →">Décrire la pièce →</a></article>
  <article class="fjm-offer"><span class="fjm-offer-icon" aria-hidden="true">⬡</span><h3 data-fjm-en="Custom accessories">Accessoires sur mesure</h3><p data-fjm-en="Mounts, holders and adapters designed around your equipment and how you use it.">Supports, porte-objets et adaptateurs pensés pour votre équipement et votre usage.</p><a href="/soumission" data-fjm-en="Start a custom quote →">Demander une soumission →</a></article>
  <article class="fjm-offer"><span class="fjm-offer-icon" aria-hidden="true">✳</span><h3 data-fjm-en="Gifts and decor">Cadeaux et décoration</h3><p data-fjm-en="Personalized keepsakes, home accents and small-batch ideas made to order.">Souvenirs personnalisés, objets déco et petites séries fabriqués à la demande.</p><a href="/galerie" data-fjm-en="Browse the gallery →">Voir les réalisations →</a></article>
  <article class="fjm-offer"><span class="fjm-offer-icon" aria-hidden="true">▱</span><h3 data-fjm-en="Print from your file">Impression depuis votre fichier</h3><p data-fjm-en="Have an STL or 3MF? Attach it to your request and tell us the quantity, colour and intended use.">Vous avez un STL ou un 3MF? Joignez-le et indiquez la quantité, la couleur et l’utilisation.</p><a href="/soumission" data-fjm-en="Send my 3D file →">Envoyer mon fichier 3D →</a></article>
 </div>
</section>
<section class="fjm-section" id="realisations">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Ready for production">Prêts à produire</span><h2 data-fjm-en="Choose a part and we will handle the printing">Choisissez une pièce, nous nous occupons de l’impression</h2><span class="fjm-ready-count" data-fjm-en="{{featured|length}} models ready with STL/3MF">✓ {{featured|length}} modèles avec fichier STL/3MF</span><p data-fjm-en="Every piece shown has an STL or 3MF already linked. Request a quote and the right model will follow automatically.">Chaque pièce présentée a son STL ou 3MF déjà associé. Demandez une soumission : le bon modèle suivra automatiquement.</p></div>
 <div class="fjm-showcase-toolbar" aria-label="Commandes du diaporama des réalisations"><button type="button" id="fjmFeaturedPrev" aria-label="Réalisations précédentes">‹</button><span id="fjmFeaturedCounter" aria-live="off">1–3</span><button type="button" id="fjmFeaturedNext" aria-label="Réalisations suivantes">›</button><button type="button" id="fjmFeaturedPause" aria-label="Mettre le diaporama en pause" aria-pressed="false">Ⅱ</button></div>
 <div class="fjm-showcase"><div class="fjm-gallery fjm-featured-track" id="fjmFeaturedTrack" tabindex="0" role="region" aria-roledescription="carrousel" aria-label="Projets avec fichier STL ou 3MF">
 {% for item in featured %}<article class="fjm-project" aria-label="Réalisation : {{item.title}}"><a class="fjm-project-image-link" href="/galerie/{{item.id}}" aria-label="Voir les photos de {{item.title}}"><img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250"></a><div class="fjm-project-content"><span>{{item.category}}</span>{% if item.is_real_piece %}<span class="fjm-photo-real-badge" data-fjm-en="✓ Made in our workshop">✓ Pièce réelle de l’atelier</span>{% endif %}{% if item.is_real_photo %}<span class="fjm-photo-real-badge" data-fjm-en="📸 Real photo">📸 Photo réelle</span>{% else %}<span class="fjm-photo-render-badge" data-fjm-en="🧊 3D preview">🧊 Visuel 3D</span>{% endif %}<strong>{{item.title[:1]|upper}}{{item.title[1:]}}</strong><small class="fjm-project-model-state">✓ Le fichier STL/3MF sera joint à votre demande</small><div class="fjm-project-actions"><a class="fjm-project-details" href="/galerie/{{item.id}}"><span data-fjm-en="See photos">Voir les photos</span></a><a class="fjm-project-quote" href="/soumission?galerie={{item.id}}&amp;photo={{item.quote_photo_id}}"><span data-fjm-en="Request a quote">Demander une soumission</span></a></div></div></article>
 {% else %}<div class="card"><h3 data-fjm-en="Printable projects coming soon">Projets avec fichier 3D à venir</h3><p data-fjm-en="You can still request a custom project.">Vous pouvez aussi demander une création sur mesure.</p><a class="btn" href="/soumission" data-fjm-en="Request a quote">Demander une soumission</a></div>{% endfor %}
 </div></div><div class="fjm-section-actions"><a class="btn fjm-outline" href="/galerie" data-fjm-en="See the full gallery">Voir toute la galerie</a></div>
</section>
<section class="fjm-process-strip" id="fonctionnement" aria-label="Comment commander">
 <span class="fjm-process-label" data-fjm-en="Simple ordering">SIMPLE ET RAPIDE</span>
 <strong data-fjm-en="1. Choose a model or describe your idea">1. Choisissez un modèle ou décrivez votre idée</strong>
 <span class="fjm-process-arrow" aria-hidden="true">→</span>
 <strong data-fjm-en="2. Get a free quote">2. Recevez une soumission gratuite</strong>
 <span class="fjm-process-arrow" aria-hidden="true">→</span>
 <strong data-fjm-en="3. We print after your approval">3. Nous imprimons après votre approbation</strong>
</section>
<section class="fjm-section" id="questions" aria-labelledby="fjm-faq-title">
 <div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Good to know">BON À SAVOIR</span><h2 id="fjm-faq-title" data-fjm-en="Questions before you order?">Des questions avant de commander?</h2><p data-fjm-en="A few details to make starting your project easier.">Quelques réponses pour vous aider à démarrer votre projet.</p></div>
 <div class="fjm-faq">
  <details><summary data-fjm-en="Do I need a 3D model?">Est-ce que j’ai besoin d’un modèle 3D?</summary><p data-fjm-en="No. A photo, sketch or written description is enough to begin a custom quote. If you have an STL or 3MF, you can attach it too.">Non. Une photo, un croquis ou une description suffit pour commencer une demande sur mesure. Si vous avez un STL ou un 3MF, vous pouvez aussi le joindre.</p></details>
  <details><summary data-fjm-en="How is the price determined?">Comment le prix est-il déterminé?</summary><p data-fjm-en="It depends on the part, dimensions, material, quantity and any finishing needed. Send the details and we will confirm a quote before production.">Il dépend de la pièce, de ses dimensions, du matériau, de la quantité et de la finition souhaitée. Envoyez les détails et on confirmera le prix avant la production.</p></details>
  <details><summary data-fjm-en="Can I order a model from the gallery?">Puis-je commander un modèle de la galerie?</summary><p data-fjm-en="Yes. Models marked ready to print include an STL or 3MF that is attached automatically when you request a quote.">Oui. Les modèles identifiés « Prêts à produire » ont un STL ou un 3MF joint automatiquement à votre demande de soumission.</p></details>
  <details><summary data-fjm-en="What if I am not sure which material to choose?">Et si je ne sais pas quel matériau choisir?</summary><p data-fjm-en="Tell us how the part will be used, including any heat, outdoor or impact exposure. We will discuss suitable options with you.">Indiquez comment la pièce sera utilisée, notamment si elle sera exposée à la chaleur, à l’extérieur ou aux chocs. On discutera des options qui conviennent.</p></details>
  <details><summary data-fjm-en="Which 3D files can I attach?">Quels fichiers 3D puis-je joindre?</summary><p data-fjm-en="The quote form accepts STL and 3MF files. If you do not have a 3D file, start with a photo, sketch or description instead.">Le formulaire accepte les fichiers STL et 3MF. Si vous n’avez pas de fichier 3D, commencez plutôt avec une photo, un croquis ou une description.</p></details>
  <details><summary data-fjm-en="Can I ask about just one part?">Puis-je demander l’impression d’une seule pièce?</summary><p data-fjm-en="Yes. Enter the quantity you need in the quote form. We review each request based on the part, its use and the details you provide.">Oui. Indiquez la quantité souhaitée dans le formulaire. Nous évaluons chaque demande selon la pièce, son usage et les détails fournis.</p></details>
 </div>
</section>
"""

MARKETING_HOME_END = """
<section class="fjm-final" aria-label="Commencer un projet"><div><span class="fjm-kicker" data-fjm-en="Ready to get started?">Prêt à créer quelque chose?</span><h2 data-fjm-en="Let's bring your idea to life.">On donne vie à votre idée.</h2><p data-fjm-en="Tell us what you need. Your quote request comes with no obligation.">Expliquez-nous votre besoin. Une demande de soumission ne vous engage à rien.</p></div><a href="/soumission" class="btn" data-fjm-en="Request my free quote">Demander ma soumission gratuite</a></section>

</div>"""

MARKETING_GALLERY = """<section class="fjm-section" style="margin-top:0"><div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Our portfolio">Nos réalisations</span><h1 data-fjm-en="Ideas that took shape">Des idées devenues réalité</h1><p data-fjm-en="Browse real parts made in our workshop, shown in real photos or 3D previews. Choose a project with an STL or 3MF file to request a quote.">Découvrez les pièces réellement fabriquées par notre atelier. Certaines vignettes sont des photos réelles, d’autres des visuels 3D. Choisissez une réalisation avec fichier STL ou 3MF pour demander votre soumission.</p></div>
<div class="fjm-gallery-controls"><input type="search" id="fjmGallerySearch" placeholder="Rechercher une création…" aria-label="Rechercher dans la galerie" autocomplete="off"><select id="fjmGalleryCategory" aria-label="Filtrer par catégorie"><option value="" data-fjm-en="All categories">Toutes les catégories</option>{% for category in items|map(attribute='category')|select|unique|sort %}<option value="{{category|lower}}">{{category}}</option>{% endfor %}</select><button class="fjm-filter" id="fjmGalleryAll" type="button" aria-pressed="true" data-fjm-en="All creations">Toutes les créations</button><button class="fjm-filter" id="fjmGalleryReady" type="button" aria-pressed="false" data-fjm-en="Ready to print">Prêts à imprimer</button><button class="fjm-filter fjm-filter-real" id="fjmGalleryReal" type="button" aria-pressed="false" data-fjm-en="✓ Printed pieces">✓ Pièces imprimées</button><span id="fjmGalleryCount" class="fjm-gallery-count" aria-live="polite"></span></div>
<div class="fjm-gallery" id="fjmGalleryItems">{% for item in items %}<article class="fjm-project" data-category="{{(item.category or '')|lower}}" data-ready="{{'1' if item.has_model else '0'}}" data-real="{{'1' if item.is_real_piece else '0'}}" data-search="{{(item.title ~ ' ' ~ item.category ~ ' ' ~ item.description)|lower}}" aria-label="{{item.title}}"><a class="fjm-project-image-link" href="/galerie/{{item.id}}" aria-label="Voir {{item.title}}">{% if item.has_photo %}<img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250">{% else %}<img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'fjm-project-noimage',textContent:'🧩'}))">{% endif %}</a><div class="fjm-project-content"><span>{{item.category}}</span>{% if item.is_real_piece %}<span class="fjm-photo-real-badge" data-fjm-en="✓ Made in our workshop">✓ Pièce réelle de l’atelier</span>{% endif %}{% if item.is_real_photo %}<span class="fjm-photo-real-badge" data-fjm-en="📸 Real photo">📸 Photo réelle</span>{% else %}<span class="fjm-photo-render-badge" data-fjm-en="🧊 3D preview">🧊 Visuel 3D</span>{% endif %}<strong>{{item.title[:1]|upper}}{{item.title[1:]}}</strong>{% if item.has_model %}<small class="fjm-model-available" data-fjm-en="✓ STL/3MF file available">✓ Fichier STL/3MF disponible</small>{% endif %}<div class="fjm-project-actions"><a href="/galerie/{{item.id}}" data-fjm-en="View project">Voir le projet</a><a href="/soumission?galerie={{item.id}}&amp;photo={{item.quote_photo_id}}" data-fjm-en="Request a quote">Demander une soumission</a></div></div></article>{% else %}<p data-fjm-en="No projects published yet.">Aucune réalisation publiée pour le moment.</p>{% endfor %}</div>
<div id="fjmGalleryNoMatch" class="fjm-gallery-empty" hidden><span data-fjm-en="No project matches? Tell us what you need and we will review a custom request.">Vous ne trouvez pas le modèle recherché? Décrivez-nous votre besoin pour une création sur mesure.</span><a href="/soumission" data-fjm-en="Describe my project">Décrire mon projet</a></div><div class="fjm-section-actions"><a class="btn" href="/soumission" data-fjm-en="Request my custom project">Demander une création personnalisée</a></div></section>
"""

MARKETING_FORM_HELP = """<div class="fjm-quote-helper"><strong data-fjm-en="A clear quote with no obligation">Une soumission claire, sans obligation d'achat</strong><p data-fjm-en="No 3D file? A photo, sketch or description is enough to get started. We confirm the quote with you before production.">Pas de fichier 3D? Une photo, un croquis ou une description suffit pour commencer. Le prix est confirmé avec vous avant la production.</p><ul><li data-fjm-en="The part's intended use and approximate size">L'utilisation de la pièce et ses dimensions approximatives</li><li data-fjm-en="Desired quantity and preferred colour/material">La quantité, la couleur et le matériau souhaités</li><li data-fjm-en="A photo, sketch or STL/3MF model, if available">Une photo ou un croquis, ou un fichier STL/3MF si vous en avez un</li></ul></div>"""

MARKETING_SCRIPT = """<script>(function(){const nodes=[...document.querySelectorAll('[data-fjm-en]')];if(!nodes.length)return;for(const n of nodes)n.dataset.fjmFr=n.textContent;function apply(){let lang='fr';try{lang=localStorage.getItem('fjord-lang')==='en'?'en':'fr'}catch(e){}document.documentElement.lang=lang==='en'?'en-CA':'fr-CA';for(const n of nodes)n.textContent=lang==='en'?n.dataset.fjmEn:n.dataset.fjmFr;const search=document.getElementById('fjmGallerySearch');if(search)search.placeholder=lang==='en'?'Search projects…':'Rechercher une création…';}const sel=document.getElementById('fjord-lang');if(sel)sel.addEventListener('change',()=>setTimeout(apply,0));apply();
 /* Catalogue : le lien « Prêts à imprimer » ouvre vraiment la sélection filtrée. */
 const gallery=document.getElementById('fjmGalleryItems');
 if(gallery){
  const cards=[...gallery.querySelectorAll('.fjm-project')];
  const search=document.getElementById('fjmGallerySearch');
  const category=document.getElementById('fjmGalleryCategory');
  const allButton=document.getElementById('fjmGalleryAll');
  const readyButton=document.getElementById('fjmGalleryReady');
  const realButton=document.getElementById('fjmGalleryReal');
  const empty=document.getElementById('fjmGalleryNoMatch');
  let count=document.getElementById('fjmGalleryCount');
  if(!count){
   const controls=document.querySelector('.fjm-gallery-controls');
   if(controls){count=document.createElement('span');count.id='fjmGalleryCount';count.className='fjm-gallery-count';count.setAttribute('aria-live','polite');controls.append(count);}
  }
  let readyOnly=new URLSearchParams(location.search).get('prets')==='1';
  let realOnly=new URLSearchParams(location.search).get('photos')==='1';
  if(realOnly)readyOnly=false;
  function filterGallery(){
   const query=(search?.value||'').trim().toLocaleLowerCase();
   const selectedCategory=(category?.value||'').trim().toLocaleLowerCase();
   let shown=0,readyShown=0;
   for(const card of cards){
    const isReady=card.dataset.ready==='1';
    const matchesText=(card.dataset.search||card.textContent).toLocaleLowerCase().includes(query);
    const matchesCategory=!selectedCategory||card.dataset.category===selectedCategory;
    const isReal=card.dataset.real==='1';
    const visible=(!readyOnly||isReady)&&(!realOnly||isReal)&&matchesText&&matchesCategory;
    card.hidden=!visible;
    if(visible){shown++;if(isReady)readyShown++}
   }
   if(allButton)allButton.setAttribute('aria-pressed',String(!readyOnly&&!realOnly));
   if(readyButton)readyButton.setAttribute('aria-pressed',String(readyOnly));
   if(realButton)realButton.setAttribute('aria-pressed',String(realOnly));
   document.body.classList.toggle('fjm-real-gallery-only',realOnly);
   if(empty)empty.hidden=shown!==0;
   if(count)count.textContent=realOnly
    ?shown+' pièce'+(shown>1?'s':'')+' imprimée'+(shown>1?'s':'')
    :readyOnly
    ?shown+' modèle'+(shown>1?'s':'')+' avec fichier STL/3MF'
    :shown+' réalisation'+(shown>1?'s':'');
  }
  function setCatalogMode(mode){
   readyOnly=mode==='ready';
   realOnly=mode==='real';
   const url=new URL(location.href);
   url.searchParams.delete('prets');url.searchParams.delete('photos');
   if(readyOnly)url.searchParams.set('prets','1');
   if(realOnly)url.searchParams.set('photos','1');
   history.replaceState(null,'',url);
   filterGallery();
  }
  allButton?.addEventListener('click',()=>setCatalogMode('all'));
  readyButton?.addEventListener('click',()=>setCatalogMode('ready'));
  realButton?.addEventListener('click',()=>setCatalogMode('real'));
  search?.addEventListener('input',filterGallery);
  category?.addEventListener('change',filterGallery);
  filterGallery();
 }
 /* Carousel of real Fjord work: automatically advances only while visible,
    and pauses for reduced motion, pointer use, or keyboard focus. */
 const track=document.getElementById('fjmFeaturedTrack');
 if(track){
  const cards=[...track.querySelectorAll('.fjm-project')];
  const previous=document.getElementById('fjmFeaturedPrev');
  const next=document.getElementById('fjmFeaturedNext');
  const pause=document.getElementById('fjmFeaturedPause');
  const counter=document.getElementById('fjmFeaturedCounter');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let userPaused=reduced.matches,hovered=false,focused=false,inView=false,manualUntil=0,timer=0;
  const perPage=()=>window.matchMedia('(max-width:650px)').matches?1:
   window.matchMedia('(max-width:1000px)').matches?2:3;
  const cardStep=()=>{const card=cards[0];return card?card.getBoundingClientRect().width+(parseFloat(getComputedStyle(track).gap)||0):1};
  const maxStart=()=>Math.max(0,cards.length-perPage());
  const startIndex=()=>Math.max(0,Math.min(maxStart(),Math.round(track.scrollLeft/Math.max(cardStep(),1))));
  function sync(){
   const start=startIndex(),size=perPage(),first=cards.length?start+1:0,last=Math.min(cards.length,start+size);
   if(counter)counter.textContent=cards.length?first+'–'+last+' / '+cards.length:'0 / 0';
   if(previous)previous.disabled=start===0;
   if(next)next.disabled=start>=maxStart();
   if(pause){pause.textContent=userPaused?'▶':'Ⅱ';pause.setAttribute('aria-pressed',String(userPaused));pause.setAttribute('aria-label',userPaused?'Reprendre le diaporama':'Mettre le diaporama en pause');}
  }
  function go(delta,manual=false){
   if(!cards.length)return;
   if(manual)manualUntil=Date.now()+12000;
   const current=startIndex(),size=perPage();
   const target=delta>0?(current>=maxStart()?0:Math.min(maxStart(),current+size)):Math.max(0,current-size);
   track.scrollTo({left:target*cardStep(),behavior:reduced.matches?'instant':'smooth'});
   requestAnimationFrame(sync);
  }
  previous?.addEventListener('click',()=>go(-1,true));
  next?.addEventListener('click',()=>go(1,true));
  pause?.addEventListener('click',()=>{userPaused=!userPaused;sync();});
  track.addEventListener('scroll',sync,{passive:true});
  track.addEventListener('pointerdown',()=>{manualUntil=Date.now()+12000;},{passive:true});
  track.addEventListener('keydown',event=>{
   if(event.target.closest('a,button,input,select,textarea'))return;
   if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();go(event.key==='ArrowRight'?1:-1,true);}
  });
  track.addEventListener('mouseenter',()=>{hovered=true;});
  track.addEventListener('mouseleave',()=>{hovered=false;});
  track.addEventListener('focusin',()=>{focused=true;});
  track.addEventListener('focusout',()=>{focused=track.contains(document.activeElement);});
  reduced.addEventListener('change',event=>{userPaused=event.matches;sync();});
  window.addEventListener('resize',sync,{passive:true});
  if('IntersectionObserver' in window){new IntersectionObserver(entries=>{inView=entries.some(entry=>entry.isIntersecting);},{threshold:.12}).observe(track);}else{inView=true;}
  timer=window.setInterval(()=>{if(inView&&!userPaused&&!hovered&&!focused&&!document.hidden&&Date.now()>=manualUntil)go(1);},7000);
  window.addEventListener('pagehide',()=>window.clearInterval(timer),{once:true});
  sync();
 }
})();</script>"""
