fx_version 'cerulean'

game 'gta5'

loadscreen 'html/index.html'
loadscreen_manual_shutdown 'yes'
loadscreen_cursor 'yes'

shared_script 'config/config.lua'
client_script 'client/client.lua'

files {
  'html/index.html',
  'html/assets/css/style.css',
  'html/assets/js/app.js',
  'html/assets/fonts/*',
  'html/assets/images/*',
  'html/assets/images/**/*',
  'html/assets/music/*',
  'html/assets/music/**/*',
  'html/assets/video/*',
  'html/assets/video/**/*'
}
