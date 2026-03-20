<#import "template.ftl" as layout>
<@layout.emailLayout>
  <div class="header">
    <h1>Verifica il tuo indirizzo email</h1>
    <p>Today Events</p>
  </div>
  <div class="body">
    <p>Ciao <strong>${user.firstName!""}</strong>,</p>
    <p>Per completare la registrazione del tuo account, verifica il tuo indirizzo email cliccando il pulsante qui sotto.</p>

    <div style="text-align: center; margin: 24px 0;">
      <a href="${link}" class="btn">Verifica email</a>
    </div>

    <p class="muted">Questo link scade tra ${linkExpirationFormatter(linkExpiration)}.</p>

    <div class="divider"></div>

    <p class="muted">Se non riesci a cliccare il pulsante, copia e incolla questo link nel browser:</p>
    <p class="link-fallback">${link}</p>

    <div class="divider"></div>

    <p class="muted">Se non hai creato un account su Today Events, ignora questa email.</p>
  </div>
  <div class="footer">
    <p>Today Events &mdash; Gestione eventi</p>
  </div>
</@layout.emailLayout>
