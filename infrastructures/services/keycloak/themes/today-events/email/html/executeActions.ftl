<#import "template.ftl" as layout>
<@layout.emailLayout>
  <div class="header">
    <h1>Benvenuto su Today Events</h1>
    <p>Il tuo account è stato creato</p>
  </div>
  <div class="body">
    <p>Ciao <strong>${user.firstName!""}</strong>,</p>
    <p>Un amministratore ha creato un account per te sulla piattaforma Today Events.</p>

    <div class="info-box">
      <div class="label">Username</div>
      <div class="value">${user.username}</div>
    </div>

    <#if user.email?has_content>
    <div class="info-box">
      <div class="label">Email</div>
      <div class="value">${user.email}</div>
    </div>
    </#if>

    <p>Per attivare il tuo account e impostare la password, clicca il pulsante qui sotto.</p>

    <div style="text-align: center; margin: 24px 0;">
      <a href="${link}" class="btn">Attiva account</a>
    </div>

    <p class="muted">Questo link scade tra ${linkExpirationFormatter(linkExpiration)}.</p>

    <div class="divider"></div>

    <p class="muted">Se non riesci a cliccare il pulsante, copia e incolla questo link nel browser:</p>
    <p class="link-fallback">${link}</p>

    <div class="divider"></div>

    <p class="muted">Dopo l'attivazione potrai accedere a tutti i servizi della piattaforma con le tue credenziali.</p>
  </div>
  <div class="footer">
    <p>Today Events &mdash; Gestione eventi</p>
  </div>
</@layout.emailLayout>
