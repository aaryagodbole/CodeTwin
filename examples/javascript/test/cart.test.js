import test from 'node:test';
import { total } from '../src/cart.js';

test('total runs', () => { total(2, 3); });
