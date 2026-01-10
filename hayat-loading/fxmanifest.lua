fx_version 'cerulean'

game 'gta5'

loadscreen 'html/index.html'
loadscreen_manual_shutdown 'yes'
ui_page 'html/index.html'

shared_script 'config/config.lua'
client_script 'client/client.lua'

files {
  'html/index.html',
  'html/assets/css/style.css',
  'html/assets/js/app.js',
  'html/assets/fonts/*',
  'html/assets/images/*',
  'html/assets/music/*',
  'html/assets/video/*'
}
