"""Check document click timing and the complete double-click visual sequence."""

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def card(page, title):
    return page.locator('.document-card').filter(has_text=title)


def observe_selection(page):
    page.evaluate("""() => {
      window.selectionTransitions = [];
      const snapshot = () => {
        const cards = [...document.querySelectorAll('.document-card')].map(card => ({
          selected: card.classList.contains('document-selected'),
          pressed: card.querySelector('.document-open').getAttribute('aria-pressed'),
          badge: !!card.querySelector('.document-selection-badge'),
          border: getComputedStyle(card).borderColor,
          shadow: getComputedStyle(card).boxShadow
        }));
        window.selectionTransitions.push({cards, count: document.querySelector('#selectionCount').textContent});
      };
      snapshot();
      window.selectionObserver?.disconnect();
      window.selectionObserver = new MutationObserver(snapshot);
      window.selectionObserver.observe(document.body, {subtree: true, childList: true, attributes: true, characterData: true});
    }""")


def assert_no_visual_change(page):
    states = page.evaluate("window.selectionObserver.disconnect(); selectionTransitions")
    assert states and all(state == states[0] for state in states), states


def pen_click(button, detail):
    button.evaluate("""(button, detail) => {
      button.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'pen'}));
      button.dispatchEvent(new PointerEvent('click', {bubbles: true, pointerType: 'pen', detail}));
      if (detail === 2) button.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, detail: 2}));
    }""", detail)


def observe_click_boundary(page, button):
    button.evaluate("""button => {
      window.clickBoundaryEvents = [];
      const id = button.closest('.document-card').dataset.documentId;
      for (const type of ['pointerdown', 'click', 'dblclick']) {
        document.addEventListener(type, event => {
          if (event.target.closest('.document-card')?.dataset.documentId !== id) return;
          window.clickBoundaryEvents.push({
            type, detail: event.detail, pointerType: event.pointerType,
            at: performance.now()
          });
        });
      }
      new MutationObserver(mutations => {
        for (const mutation of mutations) {
          const card = mutation.target;
          if (!card.matches?.('.document-card') || card.dataset.documentId !== id) continue;
          window.clickBoundaryEvents.push({
            type: 'selection', selected: card.classList.contains('document-selected'),
            at: performance.now()
          });
        }
      }).observe(document.body, {subtree: true, attributes: true, attributeFilter: ['class']});
    }""")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        server = start_server(folder, port)
        try:
            seed(folder, pdf_bytes(1), 'pdf', 'First PDF')
            seed(folder, pdf_bytes(1), 'pdf', 'Second PDF')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 900, 'height': 750})
                page.goto(f'http://127.0.0.1:{port}/login')
                page.locator('#password').fill('double-click-password')
                page.locator('#password_confirmation').fill('double-click-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_function("document.querySelectorAll('.document-card').length === 2")
                first, second = card(page, 'First PDF'), card(page, 'Second PDF')
                button = first.locator('.document-open')
                assert page.locator('.document-selected-open').count() == 0
                assert first.locator('.document-copy').locator('h3').count() == 1
                assert first.locator('.document-copy').locator('button, a, p').count() == 0
                assert page.locator('#openSelected').is_disabled()

                observe_click_boundary(page, button)
                bounds = button.bounding_box()
                point = (bounds['x'] + bounds['width'] / 2, bounds['y'] + bounds['height'] / 2)
                page.mouse.click(*point, click_count=1)
                page.wait_for_timeout(200)
                page.mouse.move(*point)
                page.mouse.down(click_count=2)
                page.mouse.up(click_count=2)
                page.locator('#reader').wait_for(state='visible')
                inside = page.evaluate('clickBoundaryEvents')
                assert not any(event['type'] == 'selection' for event in inside), inside
                assert [event['detail'] for event in inside if event['type'] == 'click'] == [1, 2], inside
                inside_down = [event for event in inside if event['type'] == 'pointerdown']
                inside_first = next(event for event in inside if event['type'] == 'click')
                assert 180 <= inside_down[1]['at'] - inside_first['at'] < 300, inside
                page.locator('#readerClose').click()

                page.evaluate('clickBoundaryEvents = []')
                page.mouse.click(*point, click_count=1)
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'", timeout=450)
                outside_before = page.evaluate('clickBoundaryEvents')
                first_click = next(event for event in outside_before if event['type'] == 'click')
                tick = next(event for event in outside_before if event['type'] == 'selection' and event['selected'])
                assert 250 <= tick['at'] - first_click['at'] <= 450, outside_before
                page.mouse.move(*point)
                page.mouse.down(click_count=2)
                page.mouse.up(click_count=2)
                outside = page.evaluate('clickBoundaryEvents')
                assert any(event['type'] == 'dblclick' for event in outside), outside
                assert page.locator('#reader').is_hidden(), outside
                page.wait_for_timeout(350)
                assert page.locator('#reader').is_hidden(), page.evaluate('clickBoundaryEvents')
                if page.locator('#clearSelection').is_enabled():
                    page.locator('#clearSelection').click()

                page.evaluate('clickBoundaryEvents = []')
                page.mouse.click(*point, click_count=1)
                page.wait_for_timeout(200)
                page.mouse.move(*point)
                page.mouse.down(click_count=2)
                page.mouse.move(0, 0)
                page.mouse.up(click_count=2)
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'", timeout=450)
                assert page.locator('#reader').is_hidden()
                page.locator('#clearSelection').click()

                page.evaluate('clickBoundaryEvents = []')
                pen_click(button, 1)
                page.wait_for_timeout(200)
                pen_click(button, 2)
                page.locator('#reader').wait_for(state='visible')
                pen_inside = page.evaluate('clickBoundaryEvents')
                assert not any(event['type'] == 'selection' for event in pen_inside), pen_inside
                pen_down = [event for event in pen_inside if event['type'] == 'pointerdown']
                pen_first = next(event for event in pen_inside if event['type'] == 'click')
                assert 180 <= pen_down[1]['at'] - pen_first['at'] < 300, pen_inside
                page.locator('#readerClose').click()

                page.evaluate('clickBoundaryEvents = []')
                pen_click(button, 1)
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'", timeout=450)
                pen_outside_before = page.evaluate('clickBoundaryEvents')
                pen_first = next(event for event in pen_outside_before if event['type'] == 'click')
                pen_tick = next(event for event in pen_outside_before if event['type'] == 'selection' and event['selected'])
                assert 250 <= pen_tick['at'] - pen_first['at'] <= 450, pen_outside_before
                pen_click(button, 2)
                pen_outside = page.evaluate('clickBoundaryEvents')
                assert any(event['type'] == 'dblclick' for event in pen_outside), pen_outside
                assert page.locator('#reader').is_hidden(), pen_outside
                page.wait_for_timeout(350)
                assert page.locator('#reader').is_hidden(), page.evaluate('clickBoundaryEvents')
                if page.locator('#clearSelection').is_enabled():
                    page.locator('#clearSelection').click()

                button.evaluate("""button => {
                  button.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'touch'}));
                  button.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, pointerType: 'touch'}));
                  button.dispatchEvent(new PointerEvent('click', {bubbles: true, pointerType: 'touch', detail: 1}));
                }""")
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                page.locator('#clearSelection').click()

                observe_selection(page)
                first.locator('.document-open').dblclick(delay=100)
                page.locator('#reader').wait_for(state='visible')
                assert_no_visual_change(page)
                page.locator('#readerClose').click()

                first.locator('.document-open').click()
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'false'
                assert page.locator('#selectionCount').inner_text() == '0 selected'
                page.wait_for_timeout(200)
                assert page.locator('#selectionCount').inner_text() == '0 selected'
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'")
                assert first.locator('.document-selection-badge').is_visible()
                assert page.locator('.document-selected-open').count() == 0
                assert page.locator('#openSelectedDocument').input_value() == first.get_attribute('data-document-id')
                page.locator('#openSelected').click()
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('#readerTitle').inner_text() == 'First PDF'
                assert page.locator('#selectionCount').inner_text() == '1 selected'
                page.locator('#readerClose').click()

                observe_selection(page)
                first.locator('.document-open').dblclick(delay=100)
                page.locator('#reader').wait_for(state='visible')
                assert_no_visual_change(page)
                page.locator('#readerClose').click()

                page.locator('#clearSelection').click()
                first.locator('.document-open').click()
                second.locator('.document-open').click()
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'")
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '2 selected'")
                assert first.locator('.document-selection-badge').is_visible()
                assert second.locator('.document-selection-badge').is_visible()
                assert page.locator('#openSelected').is_disabled()
                page.locator('#openSelectedDocument').select_option(second.get_attribute('data-document-id'))
                assert page.locator('#openSelected').is_enabled()

                first.locator('.document-open').focus()
                page.keyboard.press('Space')
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'false'
                page.keyboard.press('Space')
                assert first.locator('.document-open').get_attribute('aria-pressed') == 'true'
                page.keyboard.press('Enter')
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#readerClose').click()
                page.locator('#openSelectedDocument').select_option(second.get_attribute('data-document-id'))
                page.locator('#openSelected').click()
                page.locator('#reader').wait_for(state='visible')
                assert page.locator('#readerTitle').inner_text() == 'Second PDF'
                assert page.locator('#selectionCount').inner_text() == '2 selected'
                page.locator('#readerClose').click()
                page.locator('#clearSelection').click()
                first.locator('.document-open').evaluate("""button => {
                  button.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'pen'}));
                  button.dispatchEvent(new PointerEvent('click', {bubbles: true, pointerType: 'pen', detail: 1}));
                }""")
                assert page.locator('#selectionCount').inner_text() == '0 selected'
                page.wait_for_function("document.querySelector('#selectionCount').textContent === '1 selected'")
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('double click: passed')
