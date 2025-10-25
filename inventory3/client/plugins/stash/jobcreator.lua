local activeStashId
local lastSnapshot

local function sendNuiMessage(payload)
    SendNUIMessage(payload)
end

local function ensureOpenInventory(stash)
    if type(OpenInventory) ~= 'function' then
        print('Chezza Inventory V3: OpenInventory() is not available')
        return
    end

    OpenInventory('jobcreator_stash', {
        stash = {
            id = stash.stashId,
            label = stash.label,
            weight = stash.weight,
            maxWeight = stash.maxWeight,
            slots = stash.slots,
            items = stash.items
        },
        player = stash.player or {},
        options = {
            allowSplit = true,
            allowStack = true
        }
    })
end

RegisterNetEvent('inventory3:client:plugins:stash:jobcreator:open', function(stash)
    if not stash then
        return
    end

    activeStashId = stash.stashId
    lastSnapshot = stash

    ensureOpenInventory(stash)

    sendNuiMessage({
        action = 'jobcreator:stash:setState',
        data = stash
    })
end)

RegisterNetEvent('inventory3:client:plugins:stash:jobcreator:update', function(stash)
    if not activeStashId or not stash or stash.stashId ~= activeStashId then
        return
    end

    lastSnapshot = stash

    sendNuiMessage({
        action = 'jobcreator:stash:setState',
        data = stash
    })
end)

RegisterNetEvent('inventory3:client:plugins:stash:jobcreator:close', function(stashId)
    if stashId and stashId ~= activeStashId then
        return
    end

    sendNuiMessage({
        action = 'jobcreator:stash:close'
    })

    activeStashId = nil
    lastSnapshot = nil
end)

RegisterNUICallback('jobcreator:stash:take', function(data, cb)
    if not activeStashId then
        cb(false)
        return
    end

    data = data or {}
    data.stashId = activeStashId

    TriggerServerEvent('inventory3:server:plugins:stash:jobcreator:transaction', 'take', data)
    cb(true)
end)

RegisterNUICallback('jobcreator:stash:put', function(data, cb)
    if not activeStashId then
        cb(false)
        return
    end

    data = data or {}
    data.stashId = activeStashId

    TriggerServerEvent('inventory3:server:plugins:stash:jobcreator:transaction', 'put', data)
    cb(true)
end)

RegisterNUICallback('jobcreator:stash:refresh', function(_, cb)
    if not activeStashId then
        cb(false)
        return
    end

    TriggerServerEvent('inventory3:server:plugins:stash:jobcreator:refresh')
    cb(true)
end)
