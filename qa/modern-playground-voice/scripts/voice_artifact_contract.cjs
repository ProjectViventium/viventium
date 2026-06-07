#!/usr/bin/env node
'use strict';

/* === VIVENTIUM START ===
 * Feature: Voice artifact QA contract.
 *
 * Purpose:
 * - Re-export the product-owned artifact detector/forbidden-key contract so QA cannot drift from
 *   runtime display/persistence cleanup.
 * === VIVENTIUM END === */

module.exports = require('../../../viventium_v0_4/LibreChat/api/server/services/viventium/voiceArtifactText');
