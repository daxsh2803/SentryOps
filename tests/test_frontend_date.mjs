import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { compareIncidents, formatDateTime, formatDate, formatTime, getTimestampMs, parseDate } from '../frontend/src/utils/date.ts';

describe('Frontend Date Utilities and Incident Comparator', () => {
  describe('parseDate and getTimestampMs', () => {
    test('parses ISO 8601 timestamps ending in Z', () => {
      const d = parseDate('2026-10-12T19:54:19.985733Z');
      assert.notEqual(d, null);
      assert.equal(getTimestampMs('2026-10-12T19:54:19.985733Z'), d.getTime());
    });

    test('normalizes naive ISO strings without timezone to UTC', () => {
      const withZ = parseDate('2026-10-12T19:54:19.985733Z');
      const withoutZ = parseDate('2026-10-12T19:54:19.985733');
      assert.notEqual(withoutZ, null);
      assert.equal(withoutZ.getTime(), withZ.getTime());
    });

    test('returns null for missing, empty, or invalid inputs', () => {
      assert.equal(parseDate(null), null);
      assert.equal(parseDate(undefined), null);
      assert.equal(parseDate(''), null);
      assert.equal(parseDate('   '), null);
      assert.equal(parseDate('not-a-date'), null);

      assert.equal(getTimestampMs(null), null);
      assert.equal(getTimestampMs(undefined), null);
      assert.equal(getTimestampMs(''), null);
      assert.equal(getTimestampMs('invalid'), null);
    });
  });

  describe('formatDateTime, formatDate, formatTime', () => {
    test('returns hyphen for null or blank inputs', () => {
      assert.equal(formatDateTime(null), '-');
      assert.equal(formatDateTime(undefined), '-');
      assert.equal(formatDateTime(''), '-');
      assert.equal(formatDateTime('  '), '-');

      assert.equal(formatDate(null), '-');
      assert.equal(formatTime(null), '-');
    });

    test('formats valid date string to local string', () => {
      const res = formatDateTime('2026-10-12T19:54:19.985733Z');
      assert.notEqual(res, '-');
      assert.equal(typeof res, 'string');
    });
  });

  describe('compareIncidents (deterministic ordering)', () => {
    test('sorts distinct timestamps in descending order (newest first)', () => {
      const inc1 = { id: 1, incident_id: 'INC-OLD', created_at: '2026-10-04T10:00:00Z' };
      const inc2 = { id: 2, incident_id: 'INC-MID', created_at: '2026-10-08T12:00:00Z' };
      const inc3 = { id: 3, incident_id: 'INC-NEW', created_at: '2026-10-12T19:00:00Z' };

      const sorted = [inc1, inc3, inc2].sort(compareIncidents);
      assert.deepEqual(sorted.map(i => i.incident_id), ['INC-NEW', 'INC-MID', 'INC-OLD']);
    });

    test('tie-breaks equal timestamps by numeric id descending', () => {
      const sameTime = '2026-10-10T12:00:00Z';
      const incA = { id: 10, incident_id: 'INC-SAME-A', created_at: sameTime };
      const incB = { id: 20, incident_id: 'INC-SAME-B', created_at: sameTime };
      const incC = { id: 5, incident_id: 'INC-SAME-C', created_at: sameTime };

      const sorted = [incA, incC, incB].sort(compareIncidents);
      assert.deepEqual(sorted.map(i => i.id), [20, 10, 5]);
      assert.deepEqual(sorted.map(i => i.incident_id), ['INC-SAME-B', 'INC-SAME-A', 'INC-SAME-C']);
    });

    test('tie-breaks equal timestamps by incident_id descending when numeric id is absent or non-numeric', () => {
      const sameTime = '2026-10-10T12:00:00Z';
      const incX = { incident_id: 'INC-100', created_at: sameTime };
      const incY = { incident_id: 'INC-200', created_at: sameTime };
      const incZ = { incident_id: 'INC-050', created_at: sameTime };

      const sorted = [incX, incZ, incY].sort(compareIncidents);
      assert.deepEqual(sorted.map(i => i.incident_id), ['INC-200', 'INC-100', 'INC-050']);
    });

    test('explicitly sorts missing, null, or invalid timestamps last', () => {
      const validOld = { id: 1, incident_id: 'INC-VALID-OLD', created_at: '2026-10-01T10:00:00Z' };
      const validNew = { id: 2, incident_id: 'INC-VALID-NEW', created_at: '2026-10-15T10:00:00Z' };
      const nullTime = { id: 3, incident_id: 'INC-NULL', created_at: null };
      const undefTime = { id: 4, incident_id: 'INC-UNDEF', created_at: undefined };
      const invalidTime = { id: 5, incident_id: 'INC-INVALID', created_at: 'not-a-timestamp' };

      const sorted = [nullTime, validOld, invalidTime, validNew, undefTime].sort(compareIncidents);

      // Valid timestamps come first in newest-to-oldest order
      assert.equal(sorted[0].incident_id, 'INC-VALID-NEW');
      assert.equal(sorted[1].incident_id, 'INC-VALID-OLD');

      // The 3 missing/invalid items are placed at the bottom, tie-broken by id descending
      assert.equal(sorted[2].id, 5); // INC-INVALID
      assert.equal(sorted[3].id, 4); // INC-UNDEF
      assert.equal(sorted[4].id, 3); // INC-NULL
    });
  });
});
