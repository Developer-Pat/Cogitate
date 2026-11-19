/* eslint-disable @typescript-eslint/no-explicit-any */
// eslint-disable-next-line storybook/no-renderer-packages
import type { Meta, StoryObj } from '@storybook/react';
import { useForm } from 'react-hook-form';
import { FormCheckbox } from './FormCheckbox';

/**
 * FormCheckbox is a reusable checkbox component that integrates with react-hook-form.
 *
 * Features:
 * - Checked/unchecked states
 * - Error state display
 * - Help text support
 * - Disabled state
 * - Required field indicator
 * - Accessible labels
 */
const meta = {
  title: 'Components/Forms/FormCheckbox',
  component: FormCheckbox,
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
      description: 'Label text for the checkbox',
    },
    name: {
      control: 'text',
      description: 'Name attribute for form integration',
    },
    required: {
      control: 'boolean',
      description: 'Whether the field is required',
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the checkbox is disabled',
    },
    helpText: {
      control: 'text',
      description: 'Help text displayed below the checkbox',
    },
  },
} satisfies Meta<typeof FormCheckbox>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default checkbox
 */
export const Default: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'I agree to the terms',
    name: 'terms',
  },
};

/**
 * Checkbox for accepting terms and conditions
 */
export const TermsAndConditions: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'I accept the Terms and Conditions',
    name: 'acceptTerms',
    required: true,
  },
};

/**
 * Checkbox for newsletter subscription
 */
export const Newsletter: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Subscribe to our newsletter',
    name: 'newsletter',
    helpText: 'Receive updates about new features and improvements',
  },
};

/**
 * Checkbox for privacy policy
 */
export const PrivacyPolicy: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'I have read and agree to the Privacy Policy',
    name: 'privacyPolicy',
    required: true,
    helpText: 'Your data will be protected according to our privacy policy',
  },
};

/**
 * Required checkbox with indicator
 */
export const Required: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Enable notifications',
    name: 'notifications',
    required: true,
  },
};

/**
 * Disabled checkbox
 */
export const Disabled: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'This feature is not available',
    name: 'unavailable',
    disabled: true,
  },
};

/**
 * Disabled and checked checkbox
 */
export const DisabledChecked: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Default enabled feature',
    name: 'defaultEnabled',
    disabled: true,
  },
};

/**
 * Checkbox with error state
 */
export const WithError: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'I agree to the terms',
    name: 'terms',
    required: true,
    error: {
      message: 'You must agree to the terms to continue',
    } as any,
  },
};

/**
 * Checkbox with error and help text
 */
export const ErrorWithHelpText: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Enable two-factor authentication',
    name: 'twoFactor',
    required: true,
    error: {
      message: 'Two-factor authentication is required for this account',
    } as any,
    helpText: 'This will enhance your account security',
  },
};

/**
 * Checkbox with long label
 */
export const LongLabel: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'I understand that this action cannot be undone and will permanently delete all associated data',
    name: 'confirmDelete',
    required: true,
  },
};

/**
 * Interactive example with all features
 */
export const Interactive: Story = {
  render: (args) => <FormCheckbox {...(args as any)} />,
  // @ts-expect-error - register is provided by decorator
  args: {
    label: 'Enable feature',
    name: 'feature',
    required: false,
    disabled: false,
    helpText: 'Toggle this to enable or disable the feature',
  },
};
