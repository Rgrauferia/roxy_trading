/* Load the local globe renderer only on demand. No map, tiles or data are loaded here. */
(function (global) {
  'use strict';

  const STYLE_PATH = '/assets/vendor/maplibre-gl.css?v=1';
  const SCRIPT_PATH = '/assets/vendor/maplibre-gl.js?v=1';
  const TIMEOUT_MS = 15000;
  const readyStyles = new WeakSet();
  const failedResources = new WeakSet();
  let pending = null;
  let completed = null;

  function validLibrary() {
    const api = global.maplibregl;
    return Boolean(api && ['Map', 'NavigationControl', 'AttributionControl'].every(key => typeof api[key] === 'function'));
  }

  function failure(code, message) {
    const error = new Error(message);
    error.name = 'RoxyMapLibreLoadError';
    error.code = code;
    return error;
  }

  function stylesheetReady(element) {
    if (!element || !element.isConnected || element.disabled) return false;
    // A pre-existing, loaded local stylesheet need not fire another load event.
    return readyStyles.has(element) || Boolean(element.sheet);
  }

  function matchingResource(document, kind, resourcePath) {
    const attribute = kind === 'style' ? 'href' : 'src';
    const selector = kind === 'style' ? 'link[rel~="stylesheet"]' : 'script[src]';
    const expected = new URL(resourcePath, document.baseURI).href;
    return Array.from(document.querySelectorAll(selector)).find(element => {
      if (failedResources.has(element) || !element.isConnected || (kind === 'style' && element.disabled)) return false;
      try { return new URL(element[attribute], document.baseURI).href === expected; }
      catch (_error) { return false; }
    });
  }

  function load() {
    if (pending) return pending.promise;
    if (completed && completed.api === global.maplibregl && validLibrary() && stylesheetReady(completed.style)) return completed.promise;

    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    const attempt = { promise, resources: [], style: null, styleReady: false, scriptReady: validLibrary(), timer: null, settled: false };
    pending = attempt;

    const current = () => pending === attempt && !attempt.settled;
    function finish(error) {
      if (!current()) return;
      attempt.settled = true;
      global.clearTimeout(attempt.timer);
      attempt.resources.forEach(resource => {
        resource.element.removeEventListener('load', resource.onLoad);
        resource.element.removeEventListener('error', resource.onError);
        if (error && !resource.ready) {
          failedResources.add(resource.element);
          // Do not remove pre-existing vendor tags owned by the host page.
          if (resource.created) resource.element.remove();
        }
      });
      pending = null;
      if (error) { completed = null; reject(error); }
      else {
        completed = { promise, api: global.maplibregl, style: attempt.style };
        resolve(global.maplibregl);
      }
    }
    function checkReady() {
      if (!current() || !attempt.styleReady || !attempt.scriptReady) return;
      if (!validLibrary()) return finish(failure('MAPLIBRE_INVALID_GLOBAL', 'El visor no terminó de inicializarse. Vuelve a intentarlo.'));
      if (!stylesheetReady(attempt.style)) return finish(failure('MAPLIBRE_STYLE_ERROR', 'No pude preparar el estilo del visor. Vuelve a intentarlo.'));
      finish();
    }
    function watch(document, kind, resourcePath) {
      let element = matchingResource(document, kind, resourcePath);
      const created = !element;
      if (created) {
        element = document.createElement(kind === 'style' ? 'link' : 'script');
        element.setAttribute('data-roxy-maplibre-loader', 'true');
        if (kind === 'style') { element.rel = 'stylesheet'; element.href = resourcePath; }
        else { element.async = true; element.src = resourcePath; }
      }
      const resource = { element, created, ready: false, onLoad: null, onError: null };
      attempt.resources.push(resource);
      if (kind === 'style') attempt.style = element;
      resource.onLoad = () => {
        if (!current() || resource.ready) return;
        if (kind === 'script' && !validLibrary()) return finish(failure('MAPLIBRE_INVALID_GLOBAL', 'El visor no terminó de inicializarse. Vuelve a intentarlo.'));
        resource.ready = true;
        if (kind === 'style') { readyStyles.add(element); attempt.styleReady = true; }
        else attempt.scriptReady = true;
        checkReady();
      };
      resource.onError = () => {
        if (!current() || resource.ready) return;
        finish(failure(kind === 'style' ? 'MAPLIBRE_STYLE_ERROR' : 'MAPLIBRE_SCRIPT_ERROR', 'No pude cargar el visor. Revisa la conexión y vuelve a intentarlo.'));
      };
      element.addEventListener('load', resource.onLoad);
      element.addEventListener('error', resource.onError);
      if (created) document.head.appendChild(element);
      if (kind === 'style' && stylesheetReady(element)) resource.onLoad();
    }

    try {
      const document = global.document;
      if (!document?.head) throw failure('MAPLIBRE_DOM_UNAVAILABLE', 'El visor no está disponible en esta pantalla.');
      attempt.timer = global.setTimeout(() => finish(failure('MAPLIBRE_LOAD_TIMEOUT', 'El visor tardó demasiado en cargar. Revisa la conexión y vuelve a intentarlo.')), TIMEOUT_MS);
      watch(document, 'style', STYLE_PATH);
      if (current() && !attempt.scriptReady) watch(document, 'script', SCRIPT_PATH);
      checkReady();
    } catch (error) {
      finish(error?.code ? error : failure('MAPLIBRE_DOM_ERROR', 'No pude iniciar el visor. Vuelve a intentarlo.'));
    }
    return promise;
  }

  global.RoxyMapLibre = Object.freeze({ load });
})(window);
