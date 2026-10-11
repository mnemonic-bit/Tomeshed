"""Check bookshelf preview timing, layout, access, and input paths in Chromium."""

import io
import sqlite3
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from browser_check_reader import port_number, seed, start_server
from test_documents import pdf_bytes


def bounds(page):
    return page.locator('#bookshelfPreviewBubble').evaluate("""bubble => {
      const box = bubble.getBoundingClientRect();
      return {left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        width: innerWidth, height: innerHeight};
    }""")


def layout(page):
    return page.locator('#bookshelfPreviewBubble').evaluate("""bubble => {
      const grid = bubble.querySelector('#bookshelfPreviewGrid');
      const gridBox = grid.getBoundingClientRect();
      const tiles = [...grid.querySelectorAll('.bookshelf-preview-tile')];
      return {
        bubbleHeight: bubble.getBoundingClientRect().height,
        gridHeight: grid.clientHeight,
        scrollHeight: grid.scrollHeight,
        scrollTop: grid.scrollTop,
        tileBounds: tiles.map(tile => {
          const box = tile.getBoundingClientRect();
          return {top: box.top - gridBox.top + grid.scrollTop,
            bottom: box.bottom - gridBox.top + grid.scrollTop};
        }),
        titleVisible: bubble.querySelector('#bookshelfPreviewTitle').getBoundingClientRect().bottom <= gridBox.top,
        closeVisible: bubble.querySelector('#bookshelfPreviewClose').getBoundingClientRect().bottom <= gridBox.top
      };
    }""")


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        port = port_number()
        server = start_server(folder, port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={'width': 1000, 'height': 1100})
                base = f'http://127.0.0.1:{port}'
                page.goto(base + '/login')
                page.locator('#password').fill('bookshelf-preview-password')
                page.locator('#password_confirmation').fill('bookshelf-preview-password')
                page.get_by_role('button', name='Set password and open library').click()
                page.wait_for_url(base + '/')
                empty = page.request.post(base + '/api/bookshelves', data={'name': 'Empty shelf', 'members': []})
                assert empty.status == 201
                page.reload()
                empty_card = page.locator('.bookshelf-card').filter(has_text='Empty shelf')
                empty_card.locator('.bookshelf-card-open').hover()
                page.wait_for_timeout(200)
                assert page.locator('#bookshelfPreviewBubble').is_hidden()
                page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                assert page.locator('#bookshelfPreviewGrid').inner_text() == 'No visible documents'
                empty_layout = layout(page)
                assert empty_layout['scrollHeight'] <= empty_layout['gridHeight'] + 1
                assert empty_layout['titleVisible'] and empty_layout['closeVisible']
                page.locator('#bookshelfPreviewClose').click()
                assert page.locator('#bookshelfPreviewBubble').is_hidden()

                ids = []
                for index in range(12):
                    document_id, _ = seed(folder, pdf_bytes(1), 'pdf', f'Preview book {index:02d}')
                    ids.append(document_id)
                    if index % 2 == 0:
                        image = Image.new('RGB', (120, 180), '#51745e')
                        output = io.BytesIO(); image.save(output, 'PNG')
                        path = folder / 'storage' / 'thumbnails' / f'{document_id}.png'
                        path.parent.mkdir(exist_ok=True); path.write_bytes(output.getvalue())
                        with sqlite3.connect(folder / 'library.db') as conn:
                            conn.execute('UPDATE documents SET thumbnail_path=? WHERE id=?',
                                         (f'thumbnails/{document_id}.png', document_id))
                shelf = page.request.post(base + '/api/bookshelves', data={'name': 'Long shelf', 'members': ids})
                assert shelf.status == 201
                shelf_id = shelf.json()['id']
                single = page.request.post(base + '/api/bookshelves', data={'name': 'Single shelf', 'members': ids[:1]})
                assert single.status == 201
                pair = page.request.post(base + '/api/bookshelves', data={'name': 'Pair shelf', 'members': ids[:2]})
                assert pair.status == 201
                four = page.request.post(base + '/api/bookshelves', data={'name': 'Four shelf', 'members': ids[:4]})
                assert four.status == 201
                detail = page.request.get(base + f'/api/bookshelves/{shelf_id}').json()
                assert [item['id'] for item in detail['members']] == ids
                page.reload()
                page.locator('#librarySearch').fill('Single shelf')
                page.evaluate('() => { clearTimeout(searchTimer); return loadCatalog(); }')
                page.wait_for_function("document.querySelector('.bookshelf-card h3')?.textContent === 'Single shelf'")
                page.mouse.move(0, 0)
                page.locator('.bookshelf-card-open').hover()
                page.wait_for_function("document.querySelectorAll('#bookshelfPreviewGrid .bookshelf-preview-tile').length === 1")
                assert page.locator('#bookshelfPreviewGrid .bookshelf-preview-tile').get_attribute('aria-label') == 'Preview book 00'
                single_layout = layout(page)
                assert single_layout['scrollHeight'] <= single_layout['gridHeight'] + 1
                assert single_layout['titleVisible'] and single_layout['closeVisible']
                assert empty_layout['bubbleHeight'] < single_layout['bubbleHeight']
                page.locator('#bookshelfPreviewClose').click()
                for name, count in (('Pair shelf', 2), ('Four shelf', 4)):
                    page.locator('#librarySearch').fill(name)
                    page.evaluate('() => { clearTimeout(searchTimer); return loadCatalog(); }')
                    page.wait_for_function("name => document.querySelector('.bookshelf-card h3')?.textContent === name", arg=name)
                    page.mouse.move(0, 0)
                    page.locator('.bookshelf-card-open').hover()
                    page.wait_for_function("count => document.querySelectorAll('#bookshelfPreviewGrid .bookshelf-preview-tile').length === count", arg=count)
                    measured = layout(page)
                    assert measured['scrollHeight'] <= measured['gridHeight'] + 1, measured
                    assert measured['titleVisible'] and measured['closeVisible']
                    if count == 2:
                        assert abs(measured['bubbleHeight'] - single_layout['bubbleHeight']) < 3
                    else:
                        assert measured['bubbleHeight'] > single_layout['bubbleHeight']
                    page.locator('#bookshelfPreviewClose').click()
                page.locator('#librarySearch').fill('Long shelf')
                page.evaluate('() => { clearTimeout(searchTimer); return loadCatalog(); }')
                page.wait_for_function("document.querySelectorAll('.bookshelf-card').length === 1 && document.querySelector('.bookshelf-card h3')?.textContent === 'Long shelf'")
                card = page.locator('.bookshelf-card')
                assert card.locator('.bookshelf-cover').count() == 4
                page.mouse.move(0, 0)
                card.locator('.bookshelf-card-open').hover()
                page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                tiles = page.locator('#bookshelfPreviewGrid .bookshelf-preview-tile')
                page.wait_for_function("document.querySelectorAll('#bookshelfPreviewGrid .bookshelf-preview-tile').length === 12")
                assert tiles.count() == 12
                assert tiles.evaluate_all('(items) => items.map(item => item.getAttribute("aria-label"))') == [f'Preview book {i:02d}' for i in range(12)]
                assert page.locator('#bookshelfPreviewGrid .bookshelf-preview-fallback').count() == 6
                assert page.locator('#bookshelfPreviewGrid button, #bookshelfPreviewGrid a').count() == 0
                grid_style = page.locator('#bookshelfPreviewGrid').evaluate("""grid => ({
                  columns: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
                  scroll: grid.scrollHeight > grid.clientHeight,
                  ratio: grid.querySelector('.bookshelf-preview-art').getBoundingClientRect().width /
                    grid.querySelector('.bookshelf-preview-art').getBoundingClientRect().height,
                  fit: getComputedStyle(grid.querySelector('img')).objectFit
                })""")
                assert grid_style['columns'] == 2 and grid_style['scroll']
                assert abs(grid_style['ratio'] - 2 / 3) < 0.03 and grid_style['fit'] == 'contain'
                long_layout = layout(page)
                assert long_layout['bubbleHeight'] <= measured['bubbleHeight'] + 3, long_layout
                assert max(tile['bottom'] for tile in long_layout['tileBounds'][:4]) <= long_layout['gridHeight'] + 2, long_layout
                assert long_layout['tileBounds'][4]['top'] >= long_layout['gridHeight'] - 2, long_layout
                assert long_layout['titleVisible'] and long_layout['closeVisible']
                box = bounds(page)
                assert 0 <= box['left'] < box['right'] <= box['width']
                assert 0 <= box['top'] < box['bottom'] <= box['height']
                bubble = page.locator('#bookshelfPreviewBubble').bounding_box()
                anchor = card.locator('.bookshelf-card-open').bounding_box()
                start_x = anchor['x'] + (anchor['width'] if bubble['x'] > anchor['x'] else 0)
                end_x = bubble['x'] if bubble['x'] > anchor['x'] else bubble['x'] + bubble['width']
                y = (max(anchor['y'], bubble['y']) + min(anchor['y'] + anchor['height'], bubble['y'] + bubble['height'])) / 2
                page.mouse.move(start_x, y)
                page.mouse.move(end_x, y, steps=5)
                page.mouse.move(bubble['x'] + bubble['width'] / 2, bubble['y'] + bubble['height'] / 2)
                assert page.locator('#bookshelfPreviewBubble').is_visible()
                page.mouse.wheel(0, 120)
                page.wait_for_function("document.querySelector('#bookshelfPreviewGrid').scrollTop > 0")
                wheel_position = layout(page)['scrollTop']
                assert wheel_position < long_layout['tileBounds'][2]['top']
                page.mouse.wheel(0, 31.5)
                page.wait_for_function("position => document.querySelector('#bookshelfPreviewGrid').scrollTop > position", arg=wheel_position)
                assert abs(layout(page)['bubbleHeight'] - long_layout['bubbleHeight']) < 3
                page.locator('#bookshelfPreviewGrid').focus()
                assert page.locator('#bookshelfPreviewGrid').evaluate('grid => document.activeElement === grid')
                page.keyboard.press('End')
                page.wait_for_function("document.querySelector('#bookshelfPreviewGrid').scrollTop + document.querySelector('#bookshelfPreviewGrid').clientHeight >= document.querySelector('#bookshelfPreviewGrid').scrollHeight - 2")
                page.keyboard.press('ArrowUp')
                page.wait_for_function("document.querySelector('#bookshelfPreviewGrid').scrollTop + document.querySelector('#bookshelfPreviewGrid').clientHeight < document.querySelector('#bookshelfPreviewGrid').scrollHeight - 2")
                assert page.locator('#bookshelfPreviewBubble').is_visible()
                assert layout(page)['titleVisible'] and layout(page)['closeVisible']
                page.locator('#bookshelfPreviewGrid').evaluate('grid => grid.scrollTop = grid.scrollHeight')
                tiles.last.click()
                assert page.locator('#reader').is_hidden()
                assert page.locator('.document-selection-badge').count() == 0
                page.keyboard.press('Escape')
                assert page.locator('#bookshelfPreviewBubble').is_hidden()
                page.evaluate("document.querySelector('#documentGrid').style.justifyContent = 'flex-end'")
                page.mouse.move(0, 0)
                card.locator('.bookshelf-card-open').hover()
                page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                assert page.locator('#bookshelfPreviewBubble').get_attribute('data-side') == 'left'
                right_edge = bounds(page)
                assert 0 <= right_edge['left'] < right_edge['right'] <= right_edge['width']
                page.locator('#bookshelfPreviewClose').click()
                page.evaluate("document.querySelector('#documentGrid').style.justifyContent = ''")
                card.locator('.bookshelf-card-open').click()
                page.locator('#bookshelfDialog').wait_for(state='visible')
                page.locator('#closeBookshelfDialog').click()

                page.keyboard.press('Tab')
                card.locator('.bookshelf-card-open').focus()
                page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                assert page.locator('#bookshelfPreviewClose').evaluate('button => document.activeElement === button')
                page.keyboard.press('Escape')
                assert card.locator('.bookshelf-card-open').evaluate('button => document.activeElement === button')
                page.locator('#librarySearch').focus()

                page.set_viewport_size({'width': 1000, 'height': 450})
                page.mouse.move(0, 0)
                card.locator('.bookshelf-card-open').hover()
                page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                short = bounds(page)
                short_layout = layout(page)
                assert short['top'] >= 0 and short['bottom'] <= short['height'], short
                assert short_layout['bubbleHeight'] < long_layout['bubbleHeight']
                assert short_layout['scrollHeight'] > short_layout['gridHeight']
                assert short_layout['titleVisible'] and short_layout['closeVisible']
                page.locator('#bookshelfPreviewGrid').focus()
                page.keyboard.press('End')
                page.wait_for_function("document.querySelector('#bookshelfPreviewGrid').scrollTop > 0")
                assert page.locator('#bookshelfPreviewClose').is_visible()
                page.locator('#bookshelfPreviewClose').click()

                for viewport_width in (180, 160):
                    page.set_viewport_size({'width': viewport_width, 'height': 1200})
                    page.mouse.move(0, 0)
                    card.locator('.bookshelf-card-open').hover()
                    page.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                    narrow = bounds(page)
                    assert 0 <= narrow['left'] < narrow['right'] <= narrow['width'], narrow
                    vertical = page.locator('#bookshelfPreviewBubble').evaluate("""bubble => ({
                      top: bubble.getBoundingClientRect().top,
                      bottom: bubble.getBoundingClientRect().bottom,
                      header: document.querySelector('.app-header').getBoundingClientRect().bottom,
                      footer: document.querySelector('#versionFooter').getBoundingClientRect().top,
                      close: document.querySelector('#bookshelfPreviewClose').getBoundingClientRect().toJSON()
                    })""")
                    assert vertical['top'] >= vertical['header'] and vertical['bottom'] <= vertical['footer'], vertical
                    assert narrow['left'] <= vertical['close']['left'] < vertical['close']['right'] <= narrow['right']
                    assert page.locator('#bookshelfPreviewClose').is_visible()
                    narrow_bubble = page.locator('#bookshelfPreviewBubble').bounding_box()
                    page.mouse.move(narrow_bubble['x'] + narrow_bubble['width'] / 2,
                                    narrow_bubble['y'] + narrow_bubble['height'] / 2, steps=6)
                    assert page.locator('#bookshelfPreviewBubble').is_visible()
                    page.locator('#bookshelfPreviewClose').click()

                touch = browser.new_context(viewport={'width': 390, 'height': 750}, has_touch=True,
                                            is_mobile=True, storage_state=page.context.storage_state())
                phone = touch.new_page(); phone.goto(base + '/')
                phone.locator('#librarySearch').fill('Long shelf')
                phone.evaluate('() => { clearTimeout(searchTimer); return loadCatalog(); }')
                phone.wait_for_function("document.querySelectorAll('.bookshelf-card').length === 1 && document.querySelector('.bookshelf-card h3')?.textContent === 'Long shelf'")
                cover = phone.locator('.bookshelf-card-open')
                rect = cover.bounding_box(); x = rect['x'] + rect['width'] / 2; y = rect['y'] + rect['height'] / 2
                cdp = touch.new_cdp_session(phone)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
                phone.wait_for_timeout(200)
                assert phone.locator('#bookshelfPreviewBubble').is_hidden()
                phone.locator('#bookshelfPreviewBubble').wait_for(state='visible', timeout=2500)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                assert phone.locator('#bookshelfDialog').is_hidden()
                mobile = bounds(phone)
                assert 0 <= mobile['left'] < mobile['right'] <= mobile['width']
                assert 0 <= mobile['top'] < mobile['bottom'] <= mobile['height']
                phone_grid = phone.locator('#bookshelfPreviewGrid').bounding_box()
                touch_x = phone_grid['x'] + phone_grid['width'] / 2
                touch_y = phone_grid['y'] + phone_grid['height'] * .7
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': touch_x, 'y': touch_y}]})
                for step in range(1, 5):
                    cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': touch_x, 'y': touch_y - step * 30}]})
                    phone.wait_for_timeout(30)
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                phone.wait_for_function("document.querySelector('#bookshelfPreviewGrid').scrollTop > 0")
                assert phone.locator('#bookshelfPreviewBubble').is_visible()
                phone.locator('#bookshelfPreviewClose').tap()
                assert phone.locator('#bookshelfPreviewBubble').is_hidden()
                cover.tap()
                phone.locator('#bookshelfDialog').wait_for(state='visible')
                touch.close()

                assert page.request.post(base + '/api/users', data={'username': 'recipient', 'password': 'recipient-password', 'role': 'normal'}).status == 201
                assert page.request.post(base + f'/api/bookshelves/{shelf_id}/shares', data={'username': 'recipient'}).status == 200
                with sqlite3.connect(folder / 'library.db') as conn:
                    owner = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
                    conn.execute("UPDATE documents SET owner_user_id=?, visibility='private' WHERE id=?", (owner, ids[-1]))
                recipient = browser.new_page(viewport={'width': 1000, 'height': 700})
                recipient.goto(base + '/login')
                recipient.locator('#username').fill('recipient')
                recipient.locator('#password').fill('recipient-password')
                recipient.get_by_role('button', name='Sign in').click()
                recipient.wait_for_url(base + '/')
                recipient.locator('#librarySearch').fill('Long shelf')
                recipient.wait_for_function("document.querySelectorAll('.bookshelf-card').length === 1 && document.querySelector('.bookshelf-card h3')?.textContent === 'Long shelf'")
                recipient.locator('.bookshelf-card-open').hover()
                recipient.wait_for_function("document.querySelectorAll('#bookshelfPreviewGrid .bookshelf-preview-tile').length === 11")
                assert ids[-1] not in recipient.locator('#bookshelfPreviewGrid').inner_html()
                assert page.request.get(base + f'/api/bookshelves/{shelf_id}').json()['count'] == 12
                assert recipient.request.get(base + f'/api/bookshelves/{shelf_id}').json()['count'] == 11
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
    print('bookshelf preview: passed')
