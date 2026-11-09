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
</style>"""

MARKETING_HOME_START = """<div class="fjm-home">
<section class="fjm-hero" aria-labelledby="fjm-hero-title">
 <div><span class="fjm-kicker" data-fjm-en="Custom 3D printing in Saguenay, Québec">Impression 3D sur mesure · Saguenay, Québec</span>
 <h1 id="fjm-hero-title"><span data-fjm-en="Your idea.">Votre idée.</span> <span class="fjm-accent" data-fjm-en="Printed here.">Imprimée ici.</span></h1>
 <p class="fjm-hero-lead" data-fjm-en="Useful parts, gifts and custom creations made in Saguenay. Pick a ready-to-print model, send an STL/3MF, or start with a photo or sketch.">Pièces utiles, cadeaux et créations sur mesure fabriqués au Saguenay. Choisissez un modèle prêt à imprimer, envoyez un STL/3MF ou commencez avec une photo ou un croquis.</p>
 <div class="fjm-hero-actions"><a class="btn" href="/galerie?prets=1" data-fjm-en="Shop ready-to-print models">Voir les modèles prêts à imprimer</a><a class="btn fjm-outline" href="/soumission" data-fjm-en="Request a custom quote">Demander une soumission</a></div>
 <p class="fjm-hero-sub" data-fjm-en="No 3D file? A photo, sketch or description is enough to start · No-obligation quote">Pas de fichier 3D? Une photo, un croquis ou une description suffit · Soumission sans obligation</p>
 <ul class="fjm-points"><li data-fjm-en="⚡ Automatic STL/3MF attachment">⚡ Fichier STL/3MF joint automatiquement</li><li data-fjm-en="📍 Printed in Saguenay">📍 Imprimé au Saguenay</li><li data-fjm-en="✓ Free quote">✓ Soumission gratuite</li></ul>
 </div>
 <aside class="fjm-hero-panel fjm-hero-proof">
  <div class="fjm-hero-photo-grid" aria-label="Exemples de projets disponibles">
   {% for item in featured[:2] %}<a href="/galerie/{{item.id}}" aria-label="Voir {{item.title}}">
    <img src="/gallery/thumb/{{item.id}}" alt="{{item.title}}{% if item.is_real_photo %} — pièce imprimée en photo{% else %} — aperçu du modèle 3D{% endif %}" width="420" height="260" loading="eager" {% if loop.first %}fetchpriority="high"{% endif %}>
   </a>{% else %}<a href="/galerie" class="fjm-hero-photo-placeholder" aria-label="Découvrir la galerie">🧊<br>Projets sur mesure<br>faits au Saguenay</a>{% endfor %}
  </div>
  <p class="fjm-proof-eyebrow" data-fjm-en="MADE IN SAGUENAY · CUSTOM 3D PRINTING">FABRIQUÉ AU SAGUENAY · IMPRESSION SUR MESURE</p>
  <h2 data-fjm-en="From a quick idea to a finished part">De votre idée à la pièce finie</h2>
  <p data-fjm-en="Start with a model, file, photo or sketch. We will confirm the project details before printing.">Modèle, fichier, photo ou croquis : on valide les détails de votre projet avant l’impression.</p>
 </aside>
</section>
<section class="fjm-atelier" id="atelier" aria-labelledby="fjm-atelier-title">
 <div class="fjm-atelier-mark" aria-hidden="true">🧊</div>
 <div class="fjm-atelier-copy">
  <span class="fjm-kicker" data-fjm-en="YOUR 3D WORKSHOP, ONLINE">VOTRE ATELIER 3D, EN LIGNE</span>
  <h2 id="fjm-atelier-title" data-fjm-en="See your model take shape">Visualisez votre pièce avant sa fabrication</h2>
  <p data-fjm-en="Open the 3D workshop to import an STL or 3MF, inspect your model and explore its production settings before requesting a quote.">Ouvrez l’Atelier 3D pour importer un STL ou 3MF, examiner votre modèle et explorer ses réglages avant de demander une soumission.</p>
  <div class="fjm-atelier-actions"><a class="btn" href="/atelier-3d" data-fjm-en="Open the 3D workshop">🧊 Ouvrir l’Atelier 3D</a><a class="fjm-atelier-secondary" href="/soumission" data-fjm-en="I need help with my project">Je veux de l’aide pour mon projet</a></div>
 </div>
 <div class="fjm-atelier-note"><strong data-fjm-en="Have a 3D file?">Vous avez un fichier 3D?</strong><span>STL · 3MF</span></div>
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
 {% for item in featured %}<article class="fjm-project" aria-label="Réalisation : {{item.title}}"><a class="fjm-project-image-link" href="/galerie/{{item.id}}" aria-label="Voir les photos de {{item.title}}"><img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250"></a><div class="fjm-project-content"><span>{{item.category}}</span>{% if item.is_real_photo %}<span class="fjm-photo-real-badge" data-fjm-en="Photo of a real printed part">📷 Pièce imprimée en photo</span>{% else %}<span class="fjm-photo-render-badge" data-fjm-en="3D model preview">🧩 Aperçu du modèle 3D</span>{% endif %}<strong>{{item.title[:1]|upper}}{{item.title[1:]}}</strong><small class="fjm-project-model-state">✓ Le fichier STL/3MF sera joint à votre demande</small><div class="fjm-project-actions"><a class="fjm-project-details" href="/galerie/{{item.id}}"><span data-fjm-en="See photos">Voir les photos</span></a><a class="fjm-project-quote" href="/soumission?galerie={{item.id}}&amp;photo={{item.quote_photo_id}}"><span data-fjm-en="Request a quote">Demander une soumission</span></a></div></div></article>
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
 </div>
</section>
"""

MARKETING_HOME_END = """
<section class="fjm-final" aria-label="Commencer un projet"><div><span class="fjm-kicker" data-fjm-en="Ready to get started?">Prêt à créer quelque chose?</span><h2 data-fjm-en="Let's bring your idea to life.">On donne vie à votre idée.</h2><p data-fjm-en="Tell us what you need. Your quote request comes with no obligation.">Expliquez-nous votre besoin. Une demande de soumission ne vous engage à rien.</p></div><a href="/soumission" class="btn" data-fjm-en="Request my free quote">Demander ma soumission gratuite</a></section>

</div>"""

MARKETING_GALLERY = """<section class="fjm-section" style="margin-top:0"><div class="fjm-heading"><span class="fjm-kicker" data-fjm-en="Our portfolio">Nos réalisations</span><h1 data-fjm-en="Ideas that took shape">Des idées devenues réalité</h1><p data-fjm-en="See real photos of printed parts and 3D model previews. Choose a project with an STL or 3MF file to attach it to your quote request.">Repérez les pièces réellement imprimées et les aperçus de modèles 3D. Choisissez un projet avec fichier STL ou 3MF pour le joindre à votre demande de soumission.</p></div>
<div class="fjm-gallery-controls"><input type="search" id="fjmGallerySearch" placeholder="Rechercher une création…" aria-label="Rechercher dans la galerie" autocomplete="off"><button class="fjm-filter" id="fjmGalleryAll" type="button" aria-pressed="true" data-fjm-en="All creations">Toutes les créations</button><button class="fjm-filter" id="fjmGalleryReady" type="button" aria-pressed="false" data-fjm-en="Ready to print">Prêts à imprimer</button><span id="fjmGalleryCount" class="fjm-gallery-count" aria-live="polite"></span></div>
<div class="fjm-gallery" id="fjmGalleryItems">{% for item in items %}<article class="fjm-project" data-ready="{{'1' if item.has_model else '0'}}" data-search="{{(item.title ~ ' ' ~ item.category ~ ' ' ~ item.description)|lower}}" aria-label="{{item.title}}"><a class="fjm-project-image-link" href="/galerie/{{item.id}}" aria-label="Voir {{item.title}}">{% if item.has_photo %}<img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250">{% else %}<img src="/gallery/thumb/{{item.id}}" loading="lazy" alt="{{item.title}}" width="400" height="250" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'fjm-project-noimage',textContent:'🧩'}))">{% endif %}</a><div class="fjm-project-content"><span>{{item.category}}</span>{% if item.is_real_photo %}<span class="fjm-photo-real-badge" data-fjm-en="Photo of a real printed part">📷 Pièce imprimée en photo</span>{% else %}<span class="fjm-photo-render-badge" data-fjm-en="3D model preview">🧩 Aperçu du modèle 3D</span>{% endif %}<strong>{{item.title[:1]|upper}}{{item.title[1:]}}</strong>{% if item.has_model %}<small class="fjm-model-available" data-fjm-en="✓ STL/3MF file available">✓ Fichier STL/3MF disponible</small>{% endif %}<div class="fjm-project-actions"><a href="/galerie/{{item.id}}" data-fjm-en="View project">Voir le projet</a><a href="/soumission?galerie={{item.id}}&amp;photo={{item.quote_photo_id}}" data-fjm-en="Request a quote">Demander une soumission</a></div></div></article>{% else %}<p data-fjm-en="No projects published yet.">Aucune réalisation publiée pour le moment.</p>{% endfor %}</div>
<p id="fjmGalleryNoMatch" class="fjm-gallery-empty" hidden data-fjm-en="No projects match your search.">Aucune réalisation ne correspond à la recherche.</p><div class="fjm-section-actions"><a class="btn" href="/soumission" data-fjm-en="Request my custom project">Demander une création personnalisée</a></div></section>
"""

MARKETING_FORM_HELP = """<div class="fjm-quote-helper"><strong data-fjm-en="A clear quote with no obligation">Une soumission claire, sans obligation d'achat</strong><p data-fjm-en="To help us evaluate your project, please include:">Pour bien évaluer votre projet, indiquez idéalement :</p><ul><li data-fjm-en="The part's intended use and approximate size">L'utilisation de la pièce et ses dimensions approximatives</li><li data-fjm-en="Desired quantity and preferred colour/material">La quantité, la couleur et le matériau souhaités</li><li data-fjm-en="A photo, sketch or STL/3MF model, if available">Une photo ou un croquis, ou un fichier STL/3MF si vous en avez un</li></ul></div>"""

MARKETING_SCRIPT = """<script>(function(){const nodes=[...document.querySelectorAll('[data-fjm-en]')];if(!nodes.length)return;for(const n of nodes)n.dataset.fjmFr=n.textContent;function apply(){let lang='fr';try{lang=localStorage.getItem('fjord-lang')==='en'?'en':'fr'}catch(e){}for(const n of nodes)n.textContent=lang==='en'?n.dataset.fjmEn:n.dataset.fjmFr;const search=document.getElementById('fjmGallerySearch');if(search)search.placeholder=lang==='en'?'Search projects…':'Rechercher une création…';}const sel=document.getElementById('fjord-lang');if(sel)sel.addEventListener('change',()=>setTimeout(apply,0));apply();
 /* Catalogue : le lien « Prêts à imprimer » ouvre vraiment la sélection filtrée. */
 const gallery=document.getElementById('fjmGalleryItems');
 if(gallery){
  const cards=[...gallery.querySelectorAll('.fjm-project')];
  const search=document.getElementById('fjmGallerySearch');
  const allButton=document.getElementById('fjmGalleryAll');
  const readyButton=document.getElementById('fjmGalleryReady');
  const empty=document.getElementById('fjmGalleryNoMatch');
  let count=document.getElementById('fjmGalleryCount');
  if(!count){
   const controls=document.querySelector('.fjm-gallery-controls');
   if(controls){count=document.createElement('span');count.id='fjmGalleryCount';count.className='fjm-gallery-count';count.setAttribute('aria-live','polite');controls.append(count);}
  }
  let readyOnly=new URLSearchParams(location.search).get('prets')==='1';
  function filterGallery(){
   const query=(search?.value||'').trim().toLocaleLowerCase();
   let shown=0,readyShown=0;
   for(const card of cards){
    const isReady=card.dataset.ready==='1';
    const matchesText=(card.dataset.search||card.textContent).toLocaleLowerCase().includes(query);
    const visible=(!readyOnly||isReady)&&matchesText;
    card.hidden=!visible;
    if(visible){shown++;if(isReady)readyShown++}
   }
   if(allButton)allButton.setAttribute('aria-pressed',String(!readyOnly));
   if(readyButton)readyButton.setAttribute('aria-pressed',String(readyOnly));
   if(empty)empty.hidden=shown!==0;
   if(count)count.textContent=readyOnly
    ?readyShown+' modèle'+(readyShown>1?'s':'')+' avec fichier STL/3MF'
    :shown+' réalisation'+(shown>1?'s':'');
  }
  function setReadyFilter(enabled){
   readyOnly=enabled;
   const url=new URL(location.href);
   if(enabled)url.searchParams.set('prets','1');else url.searchParams.delete('prets');
   history.replaceState(null,'',url);
   filterGallery();
  }
  allButton?.addEventListener('click',()=>setReadyFilter(false));
  readyButton?.addEventListener('click',()=>setReadyFilter(true));
  search?.addEventListener('input',filterGallery);
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
