/* eslint-disable @typescript-eslint/no-explicit-any */
// eslint-disable-next-line storybook/no-renderer-packages
import type { Meta, StoryObj } from '@storybook/react';
import { useForm } from 'react-hook-form';
import { FormSelect } from './FormSelect';

/**
 * FormSelect is a reusable dropdown select component that integrates with react-hook-form.
 *
 * Features:
 * - Customizable options
 * - Error state display
 * - Help text support
 * - Disabled state
 * - Required field indicator
 * - Accessible labels
 */
const meta = {
  title: 'Components/Forms/FormSelect',
  component: FormSelect,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => {
      const { register } = useForm();
      return <Story args={{ register }} />;
    },
  ],
  argTypes: {
    label: {
      control: 'text',
      description: 'Label text for the select field',
    },
    name: {
      control: 'text',
      description: 'Name attribute for form integration',
    },
    placeholder: {
      control: 'text',
      description: 'Placeholder text',
    },
    required: {
      control: 'boolean',
      description: 'Whether the field is required',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the field is disabled',
    },
    helpText: {
      control: 'text',
      description: 'Help text displayed below the select',
    },
  },
} satisfies Meta<typeof FormSelect>;

export default meta;
type Story = StoryObj<typeof meta>;

const countryOptions = [
  { value: 'us', label: 'United States' },
  { value: 'ca', label: 'Canada' },
  { value: 'uk', label: 'United Kingdom' },
  { value: 'au', label: 'Australia' },
  { value: 'de', label: 'Germany' },
  { value: 'fr', label: 'France' },
];

const roleOptions = [
  { value: 'admin', label: 'Administrator' },
  { value: 'user', label: 'User' },
  { value: 'viewer', label: 'Viewer' },
  { value: 'editor', label: 'Editor' },
];

const agentTypeOptions = [
  { value: 'llm', label: 'Language Model' },
  { value: 'tool', label: 'Tool Agent' },
  { value: 'workflow', label: 'Workflow' },
  { value: 'custom', label: 'Custom Agent' },
];

/**
 * Default select field
 */
export const Default: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Country',
    name: 'country',
    options: countryOptions,
    placeholder: 'Select a country',
  },
};

/**
 * Select field with role options
 */
export const WithRoles: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'User Role',
    name: 'role',
    options: roleOptions,
    placeholder: 'Select a role',
    required: true,
  },
};

/**
 * Select field with agent types
 */
export const WithAgentTypes: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Agent Type',
    name: 'agentType',
    options: agentTypeOptions,
    placeholder: 'Choose an agent type',
  },
};

/**
 * Select field with help text
 */
export const WithHelpText: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Country',
    name: 'country',
    options: countryOptions,
    placeholder: 'Select a country',
    helpText: 'Select your country of residence',
  },
};

/**
 * Required select field with indicator
 */
export const Required: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'User Role',
    name: 'role',
    options: roleOptions,
    placeholder: 'Select a role',
    required: true,
  },
};

/**
 * Disabled select field
 */
export const Disabled: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Country',
    name: 'country',
    options: countryOptions,
    placeholder: 'Select a country',
    disabled: true,
  },
};

/**
 * Select field with error state
 */
export const WithError: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'User Role',
    name: 'role',
    options: roleOptions,
    placeholder: 'Select a role',
    error: {
      message: 'Please select a valid role',
    } as any,
  },
};

/**
 * Select field with error and help text
 */
export const ErrorWithHelpText: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Agent Type',
    name: 'agentType',
    options: agentTypeOptions,
    placeholder: 'Choose an agent type',
    error: {
      message: 'Agent type is required',
    } as any,
    helpText: 'Select the type of agent to create',
  },
};

/**
 * Select field with many options
 */
export const ManyOptions: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Country',
    name: 'country',
    options: [
      ...countryOptions,
      { value: 'jp', label: 'Japan' },
      { value: 'cn', label: 'China' },
      { value: 'in', label: 'India' },
      { value: 'br', label: 'Brazil' },
      { value: 'mx', label: 'Mexico' },
    ],
    placeholder: 'Select a country',
  },
};

/**
 * Interactive example with all features
 */
export const Interactive: Story = {
  render: (args) => <FormSelect {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Select Option',
    name: 'option',
    options: roleOptions,
    placeholder: 'Choose an option',
    required: false,
    disabled: false,
    helpText: 'Select from the available options',
  },
};

