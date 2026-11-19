/* eslint-disable @typescript-eslint/no-explicit-any */
// eslint-disable-next-line storybook/no-renderer-packages
import type { Meta, StoryObj } from '@storybook/react';
import { useForm } from 'react-hook-form';
import { FormInput } from './FormInput';

/**
 * FormInput is a reusable form input component that integrates with react-hook-form.
 *
 * Features:
 * - Multiple input types (text, email, password, number, url)
 * - Error state display
 * - Help text support
 * - Disabled state
 * - Required field indicator
 * - Accessible labels
 */
const meta = {
  title: 'Components/Forms/FormInput',
  component: FormInput,
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
      description: 'Label text for the input field',
    },
    name: {
      control: 'text',
      description: 'Name attribute for form integration',
    },
    type: {
      control: 'select',
      options: ['text', 'email', 'password', 'number', 'url'],
      description: 'Input type',
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
      description: 'Help text displayed below the input',
    },
  },
} satisfies Meta<typeof FormInput>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default text input field
 */
export const Default: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Username',
    name: 'username',
    type: 'text',
    placeholder: 'Enter your username',
  },
};

/**
 * Email input field
 */
export const Email: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Email Address',
    name: 'email',
    type: 'email',
    placeholder: 'you@example.com',
    required: true,
  },
};

/**
 * Password input field
 */
export const Password: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Password',
    name: 'password',
    type: 'password',
    placeholder: 'Enter your password',
    required: true,
  },
};

/**
 * Number input field
 */
export const Number: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Age',
    name: 'age',
    type: 'number',
    placeholder: 'Enter your age',
  },
};

/**
 * URL input field
 */
export const URL: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Website',
    name: 'website',
    type: 'url',
    placeholder: 'https://example.com',
  },
};

/**
 * Input field with help text
 */
export const WithHelpText: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Username',
    name: 'username',
    type: 'text',
    placeholder: 'Enter your username',
    helpText: 'Username must be 3-20 characters long',
  },
};

/**
 * Required input field with indicator
 */
export const Required: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Full Name',
    name: 'fullName',
    type: 'text',
    placeholder: 'Enter your full name',
    required: true,
  },
};

/**
 * Disabled input field
 */
export const Disabled: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Account ID',
    name: 'accountId',
    type: 'text',
    placeholder: 'Auto-generated',
    disabled: true,
  },
};

/**
 * Input field with error state
 */
export const WithError: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Email Address',
    name: 'email',
    type: 'email',
    placeholder: 'you@example.com',
    error: {
      message: 'Please enter a valid email address',
    } as any,
  },
};

/**
 * Input field with error and help text
 */
export const ErrorWithHelpText: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Password',
    name: 'password',
    type: 'password',
    placeholder: 'Enter your password',
    error: {
      message: 'Password must be at least 8 characters',
    } as any,
    helpText: 'Use a mix of uppercase, lowercase, numbers, and symbols',
  },
};

/**
 * Interactive example with all features
 */
export const Interactive: Story = {
  render: (args) => <FormInput {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Search Query',
    name: 'search',
    type: 'text',
    placeholder: 'Type to search...',
    required: false,
    disabled: false,
    helpText: 'Enter keywords to search',
  },
};

