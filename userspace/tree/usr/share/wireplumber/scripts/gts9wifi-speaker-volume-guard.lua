-- SPDX-License-Identifier: MIT
-- Guard raw hardware speaker sink ("CS35L45 Direct") volume based on which
-- output is currently selected as default:
--   - When the tuned virtual sink (gts9wifi_speaker_eq) is default:
--       keep the raw ALSA sink at 100% (1.0 linear) and unmuted so the EQ
--       filter-chain has full headroom.
--   - If anything directly selects the raw ALSA sink as default:
--       clamp/lock the raw ALSA sink to <= 20% (0.20^3 = 0.008 cubic) so it
--       can never blast unfiltered 100% audio.

local cutils = require ("common-utils")
local log = Log.open_topic ("gts9wifi-speaker-guard")

local EQ_SINK = "gts9wifi_speaker_eq"
local RAW_SINK = "alsa_output.platform-sound.HiFi__Speaker__sink"
local FULL_VOL = 1.0
local SAFE_VOL = 0.008        -- 20% cubic (0.20^3)
local SAFE_VOL_LIMIT = 0.0085 -- small epsilon to avoid re-trigger loops

local function get_default_sink_name (source)
  local om = source:call ("get-object-manager", "metadata")
  if not om then
    return nil
  end
  local metadata = om:lookup { Constraint { "metadata.name", "=", "default" } }
  if not metadata then
    return nil
  end
  local val = metadata:find (0, "default.audio.sink")
  if not val then
    return nil
  end
  local parsed = Json.Raw (val):parse ()
  if type (parsed) == "table" then
    return parsed.name
  end
  return nil
end

local function get_raw_sink_state (node)
  local ch_count = 4
  local max_vol = nil
  local min_vol = nil
  local muted = nil

  for p in node:iterate_params ("Props") do
    local props = cutils.parseParam (p, "Props")
    if props then
      if type (props.channelVolumes) == "table" and #props.channelVolumes > 0 then
        ch_count = #props.channelVolumes
        for _, v in ipairs (props.channelVolumes) do
          if max_vol == nil or v > max_vol then max_vol = v end
          if min_vol == nil or v < min_vol then min_vol = v end
        end
      end
      if props.mute ~= nil then
        muted = props.mute
      end
    end
  end

  return ch_count, min_vol, max_vol, muted
end

local function set_raw_volume (node, vol, unmute)
  local ch_count = get_raw_sink_state (node)
  local vols = { "Spa:Float" }
  for _ = 1, ch_count do
    table.insert (vols, vol)
  end

  local pod_args = {
    "Spa:Pod:Object:Param:Props", "Props",
    channelVolumes = Pod.Array (vols),
  }
  if unmute then
    pod_args.mute = false
  end

  node:set_param ("Props", Pod.Object (pod_args))
end

local function enforce_for_default (source, default_sink, raw_node)
  if not raw_node then
    local om = source:call ("get-object-manager", "node")
    if not om then
      return
    end
    raw_node = om:lookup { Constraint { "node.name", "=", RAW_SINK } }
  end
  if not raw_node then
    return
  end

  local _, min_vol, max_vol, muted = get_raw_sink_state (raw_node)

  if default_sink == EQ_SINK then
    if min_vol == nil or min_vol < 0.999 or muted == true then
      log:info ("default sink is " .. EQ_SINK .. "; setting " .. RAW_SINK .. " to 100%")
      set_raw_volume (raw_node, FULL_VOL, true)
    end
  elseif default_sink == RAW_SINK then
    if max_vol == nil or max_vol > SAFE_VOL_LIMIT then
      log:warning ("default sink is " .. RAW_SINK .. "; clamping volume to 20%")
      set_raw_volume (raw_node, SAFE_VOL, false)
    end
  end
end

-- 1. React whenever WirePlumber updates the default audio sink.
SimpleEventHook {
  name = "gts9wifi/speaker-guard-on-default-change",
  after = { "default-nodes/apply-default-node" },
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "select-default-node" },
      Constraint { "default-node.type", "=", "audio.sink" },
    },
  },
  execute = function (event)
    local source = event:get_source ()
    local selected_node = event:get_data ("selected-node")
    if selected_node then
      enforce_for_default (source, selected_node, nil)
    end
  end
}:register ()

-- 2. Enforce on startup / when the raw ALSA speaker sink appears.
SimpleEventHook {
  name = "gts9wifi/speaker-guard-on-node-added",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "node-added" },
      Constraint { "node.name", "=", RAW_SINK },
    },
  },
  execute = function (event)
    local source = event:get_source ()
    local node = event:get_subject ()
    local default_sink = get_default_sink_name (source)
    if default_sink then
      enforce_for_default (source, default_sink, node)
    end
  end
}:register ()

-- 3. Lock raw sink volume while it is active (<= 20%) or behind EQ (100%).
SimpleEventHook {
  name = "gts9wifi/speaker-guard-on-props-changed",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "node-params-changed" },
      Constraint { "event.subject.param-id", "=", "Props" },
      Constraint { "node.name", "=", RAW_SINK },
    },
  },
  execute = function (event)
    local source = event:get_source ()
    local node = event:get_subject ()
    local default_sink = get_default_sink_name (source)
    if default_sink then
      enforce_for_default (source, default_sink, node)
    end
  end
}:register ()
