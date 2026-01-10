local hasSentConfig = false

local function sendConfig()
    if hasSentConfig then
        return
    end

    hasSentConfig = true
    SendNUIMessage({
        type = 'config',
        payload = Config
    })
end

AddEventHandler('onClientResourceStart', function(resourceName)
    if resourceName ~= GetCurrentResourceName() then
        return
    end

    sendConfig()
end)

CreateThread(function()
    while not NetworkIsSessionStarted() do
        Wait(500)
    end

    Wait(1000)
    ShutdownLoadingScreenNui()
    ShutdownLoadingScreen()
end)
