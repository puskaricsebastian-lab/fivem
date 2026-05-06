document.addEventListener('DOMContentLoaded', () => {
  const apiNotice = 'Nicht verbunden – eigene API eintragen';

  const discordMembers = document.getElementById('discord-members');
  const fivemPlayers = document.getElementById('fivem-players');

  if (discordMembers) discordMembers.textContent = 'Eigene Daten hier einfügen';
  if (fivemPlayers) fivemPlayers.textContent = 'Noch nicht konfiguriert';

  console.info('LiteCrimelife Platzhalter geladen.');
  console.info(`Discord/API Status: ${apiNotice}`);
});
