import { test } from 'vitest';
import { total } from '../src/cart';

test('total runs', () => { total(2, 3); });
