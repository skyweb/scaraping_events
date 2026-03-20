<#import "template.ftl" as layout>
<@layout.emailLayout>
  <div class="header">
    <h1>Reimposta la tua password</h1>
    <p>Today Events</p>
  </div>
  <div class="body">
    <p>Ciao <strong>${user.firstName!""}</strong>,</p>
    <p>Abbiamo ricevuto una richiesta di reimpostazione della password per il tuo account.</p>

    <div style="text-align: center; margin: 24px 0;">
      <a href="${link}" class="btn">Reimposta password</a>
    </div>

    <p class="muted">Questo link scade tra ${linkExpirationFormatter(linkExpiration)}.</p>

    <div class="divider"></div>

    <p class="muted">Se non riesci a cliccare il pulsante, copia e incolla questo link nel browser:</p>
    <p class="link-fallback">${link}</p>

    <div class="divider"></div>

    <p class="muted">Se non hai richiesto la reimpostazione della password, ignora questa email. La tua password non verrà modificata.</p>
  </div>
  <div class="footer">
    <p>Today Events &mdash; Gestione eventi</p>
  </div>
</@layout.emailLayout>
