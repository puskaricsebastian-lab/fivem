local StashSessions = {}

local function closeSession(source)
    local session = StashSessions[source]

    if not session then
        return
    end

    StashSessions[source] = nil
    TriggerClientEvent('inventory3:client:plugins:stash:jobcreator:close', source, session.stashId)
end

local function cloneItem(item)
    if type(item) ~= 'table' then
        return item
    end

    local copy = {}

    for key, value in pairs(item) do
        copy[key] = value
    end

    return copy
end

local function mapItems(items)
    local mapped = {}

    if type(items) ~= 'table' then
        return mapped
    end

    for slot, item in pairs(items) do
        local normalisedSlot = tonumber(slot) or slot
        mapped[normalisedSlot] = cloneItem(item)
    end

    return mapped
end

local function normalizeStashPayload(stashId, payload)
    if type(payload) ~= 'table' then
        payload = {}
    end

    payload.stashId = payload.stashId or stashId
    payload.label = payload.label or payload.name or stashId
    payload.weight = payload.weight or payload.maxWeight
    payload.maxWeight = payload.maxWeight or payload.weight
    payload.slots = payload.slots or payload.size or 0
    payload.items = mapItems(payload.items)
    payload.player = mapItems(payload.player)
    payload.handlers = payload.handlers or {}
    payload.refreshEvent = payload.refreshEvent or payload.handlers.refresh
    payload.takeEvent = payload.takeEvent or payload.handlers.take
    payload.putEvent = payload.putEvent or payload.handlers.put

    return payload
end

local function sendSnapshot(source, snapshot)
    TriggerClientEvent('inventory3:client:plugins:stash:jobcreator:update', source, snapshot)
end

local function withSession(source, stashId)
    local session = StashSessions[source]

    if not session or session.stashId ~= stashId then
        return nil
    end

    return session
end

local function onStashItemChange(session, direction, change)
    local stashItems = session.stash.items
    local slot = tonumber(change.slot) or change.slot

    if direction == 'take' then
        if slot and stashItems[slot] then
            local item = stashItems[slot]
            item.count = (item.count or item.amount or 0) - (change.count or change.amount or 0)

            if item.count <= 0 then
                stashItems[slot] = nil
            end
        end
    elseif direction == 'put' then
        if slot then
            stashItems[slot] = cloneItem(change.item) or {
                name = change.name,
                label = change.label,
                count = change.count or change.amount,
                metadata = change.metadata,
                weight = change.weight
            }

            if stashItems[slot] then
                stashItems[slot].count = change.count or change.amount or stashItems[slot].count
                stashItems[slot].metadata = change.metadata or stashItems[slot].metadata
            end
        end
    end

    sendSnapshot(session.source, session.stash)
end

AddEventHandler('playerDropped', function()
    closeSession(source)
end)

AddEventHandler('onResourceStop', function(resourceName)
    if resourceName ~= GetCurrentResourceName() then
        return
    end

    for playerId in pairs(StashSessions) do
        closeSession(playerId)
    end
end)

RegisterNetEvent('inventory3:server:plugins:stash:jobcreator:transaction', function(action, payload)
    local src = source
    local session = StashSessions[src]

    if not session then
        return
    end

    if action ~= 'take' and action ~= 'put' then
        return
    end

    local handlerEvent = action == 'take' and session.handlers.takeEvent or session.handlers.putEvent

    if not handlerEvent then
        return
    end

    local requestId = ('jobcreator:%s:%s:%s'):format(session.stashId, action, os.time())

    local responseHandled = false

    local function respond(success, response)
        if responseHandled then
            return
        end

        responseHandled = true

        if success and type(response) == 'table' then
            if response.refresh then
                session.stash.items = response.refresh.items or session.stash.items
                session.stash.weight = response.refresh.weight or session.stash.weight
            elseif response.change then
                onStashItemChange(session, action, response.change)
                return
            end
        end

        sendSnapshot(src, session.stash)
    end

    TriggerEvent(handlerEvent, src, session.stashId, payload, respond, requestId)
end)

RegisterNetEvent('inventory3:server:plugins:stash:jobcreator:refresh', function()
    local src = source
    local session = StashSessions[src]

    if not session then
        return
    end

    local handlerEvent = session.handlers.refreshEvent

    if not handlerEvent then
        sendSnapshot(src, session.stash)
        return
    end

    TriggerEvent(handlerEvent, src, session.stashId, function(success, response)
        if not success or type(response) ~= 'table' then
            sendSnapshot(src, session.stash)
            return
        end

        session.stash.items = response.items or session.stash.items
        session.stash.weight = response.weight or session.stash.weight

        sendSnapshot(src, session.stash)
    end)
end)

exports('openExternalStash', function(source, stashId, payload)
    assert(type(source) == 'number', 'source must be a player id')
    assert(type(stashId) == 'string', 'stashId must be a string')

    payload = normalizeStashPayload(stashId, payload)

    closeSession(source)

    local session = {
        source = source,
        stashId = stashId,
        stash = {
            stashId = payload.stashId,
            label = payload.label,
            weight = payload.weight,
            maxWeight = payload.maxWeight,
            slots = payload.slots,
            items = payload.items,
            player = payload.player,
            type = 'jobcreator'
        },
        handlers = {
            takeEvent = payload.takeEvent,
            putEvent = payload.putEvent,
            refreshEvent = payload.refreshEvent
        }
    }

    StashSessions[source] = session

    TriggerClientEvent('inventory3:client:plugins:stash:jobcreator:open', source, session.stash)
end)

exports('takeFromStorage', function(source, stashId, change)
    local session = withSession(source, stashId)

    if not session then
        return
    end

    onStashItemChange(session, 'take', change or {})
end)

exports('putIntoStorage', function(source, stashId, change)
    local session = withSession(source, stashId)

    if not session then
        return
    end

    onStashItemChange(session, 'put', change or {})
end)

exports('closeExternalStash', function(source, stashId)
    local session = withSession(source, stashId)

    if not session then
        return
    end

    closeSession(source)
end)
