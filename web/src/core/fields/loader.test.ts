import { describe, expect, it, vi } from 'vitest';
import { createFieldLoader, FieldLoadError, parseFieldPath } from './loader';

describe('parseFieldPath', () => {
  it('splits extension, file and function', () => {
    expect(parseFieldPath('default.basic.password')).toEqual({ extension: 'default', file: 'basic', name: 'password' });
    expect(parseFieldPath('my-ext.fields_2.render$')).toEqual({ extension: 'my-ext', file: 'fields_2', name: 'render$' });
  });

  it('rejects anything else', () => {
    expect(parseFieldPath('<input>')).toBeNull();
    expect(parseFieldPath('default.basic')).toBeNull();
    expect(parseFieldPath('a.b.c.d')).toBeNull();
  });
});

describe('createFieldLoader', () => {
  const render = () => undefined;
  const modules = {
    '/src/modules/fields/default/basic.ts': vi.fn(async () => ({ text: render, notAFunction: 42 })),
  };

  it('loads a function from src/modules/fields/{extension}/{file}.ts', async () => {
    const loader = createFieldLoader(modules);
    await expect(loader.load('default.basic.text')).resolves.toBe(render);
    expect(loader.modules()).toEqual(['default/basic']);
  });

  it('imports each module once', async () => {
    const importer = vi.fn(async () => ({ text: render }));
    const loader = createFieldLoader({ '/src/modules/fields/acme/widgets.ts': importer });
    await loader.load('acme.widgets.text');
    await loader.load('acme.widgets.text');
    expect(importer).toHaveBeenCalledTimes(1);
  });

  it('explains which module or export is missing', async () => {
    const loader = createFieldLoader(modules);
    await expect(loader.load('acme.widgets.color')).rejects.toThrow(/src\/modules\/fields\/acme\/widgets\.ts/);
    await expect(loader.load('default.basic.missing')).rejects.toThrow(/does not export a function "missing"/);
    await expect(loader.load('default.basic.notAFunction')).rejects.toBeInstanceOf(FieldLoadError);
    await expect(loader.load('not a path')).rejects.toBeInstanceOf(FieldLoadError);
  });
});
