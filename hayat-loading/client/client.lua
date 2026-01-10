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

CreateThread(function()
    SetNuiFocus(false, false)
    sendConfig()

    local progress = 0
    while progress < 100 do
        progress = math.min(progress + math.random(1, 4), 100)
        SendNUIMessage({
            type = 'progress',
            value = progress
        })
        Wait(200)
    end
end)

AddEventHandler('onClientResourceStart', function(resourceName)
    if resourceName ~= GetCurrentResourceName() then
        return
    end

    sendConfig()
end)
